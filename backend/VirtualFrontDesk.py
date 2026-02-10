import time
import uvicorn
import requests
import threading
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List, Optional
from SessionManager import SessionManager
from ChromaDBService import ChromaDBService
import pytz
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    error: Optional[str] = None


class PromptRequest(BaseModel):
    prompt: str
    conversationSession: str
    username: Optional[str] = None


class PromptResponse(BaseModel):
    success: bool
    response: str
    requires_auth: bool = False
    intent: Optional[str] = None


class VirtualFrontDesk(ChromaDBService):
    """Virtual Front Desk for The Lewis College student inquiries."""

    def __init__(self):
        load_dotenv()
        super().__init__()
        self.session_manager = SessionManager(max_history_per_session=4)
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        self.intents = {
            "schedule": "asking about class schedule, timetable, or next class",
            "grades": "asking about grades, marks, GPA, or academic performance",
            "soa": "asking about statement of account, balance, assessment fees",
            "clearance": "asking about academic clearance",
            "general": "asking about general questions such as enrollments, programs, courses, fees"
        }
        
        self.program_keywords = {
            'bsba_om': ['operations management', 'bsba om', 'bsba-om'],
            'bsba_fm': ['financial management', 'bsba fm', 'bsba-fm'],
            'bsba_mm': ['marketing management', 'bsba mm', 'bsba-mm'],
            'bsentrep': ['entrepreneurship', 'bsentrep', 'bs entrep'],
            'bsit': ['bsit', 'information technology', 'it student'],
            'bsed_math': ['bsed math', 'bsed-math', 'mathematics teacher'],
            'bsed_english': ['bsed english', 'bsed-eng', 'english teacher'],
            'beed': ['beed', 'elementary education', 'elementary teacher'],
            'act_network': ['networking', 'act network', 'act-network'],
            'act_data': ['data engineering', 'act data', 'act-data'],
            'act_appdev': ['applications development', 'act app'],
            'tcp': ['teacher certificate', 'tcp'],
        }

    def store_student_session(self, username: str, session: requests.Session) -> None:
        """Store authenticated user session."""
        print(f"Stored session for user: {username}")

    def detect_intent(self, prompt: str) -> str:
        """Detect intent from user prompt using embeddings."""
        try:
            prompt_embedding = self.get_embedding(prompt)
            
            intent_embeddings = {}
            for intent_name, description in self.intents.items():
                intent_embedding = self.get_embedding(description)
                intent_embeddings[intent_name] = intent_embedding
            
            similarities = {}
            for intent_name, intent_embedding in intent_embeddings.items():
                similarity = self.calculate_cosine_similarity(prompt_embedding, intent_embedding)
                similarities[intent_name] = similarity
            
            return max(similarities, key=similarities.get)
        except Exception as e:
            print(f"Error detecting intent: {e}")
            return "general"

    def _extract_program_from_query(self, prompt: str) -> Optional[str]:
        """Extract program identifier from user query."""
        prompt_lower = prompt.lower()
        
        for program_id, keywords in self.program_keywords.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    print(f"📌 Detected program context: {program_id}")
                    return program_id
        
        return None

    def _create_system_prompt_strict(self, context: str, history: List[dict] = None) -> str:
        """Create STRICT system prompt for GPT-4o."""
        if history is None:
            history = []

        ph_time = datetime.now(pytz.timezone("Asia/Manila"))
        hour = ph_time.hour
        if 5 <= hour < 12:
            greeting = "Good morning"
        elif 12 <= hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        return f"""You are TLC ChatMate, the official virtual front desk of The Lewis College.

📌 PURPOSE: Provide immediate, accurate academic and administrative assistance using only verified college documents.

{greeting}! I'm here to help with your questions about enrollment, programs, policies, and services at The Lewis College.

CRITICAL INSTRUCTIONS - MUST FOLLOW:
1. Answer ONLY using the provided database information below.
2. Do NOT use general knowledge, assumptions, or external facts.
3. If exact info isn't in the database, say: "I'm sorry, but I don't have information about [topic] in our current records."
4. For greetings → respond warmly with "{greeting}!" once, then assist.
5. For farewells → reply politely and end conversation.
6. If user uses disruptive/inappropriate language:
   - Stay calm, neutral, and professional.
   - Do NOT react emotionally.
   - Respond briefly: "Let's keep our conversation respectful and focused on your academic needs."
7. NEVER insult, argue, or mirror inappropriate tone.

RESPONSE RULES:
- Keep answers concise (1–3 sentences unless listing requirements).
- Use bullet points ONLY for: enrollment steps, fees, scholarships, checklists.
- Language: English, Tagalog, or Bicol. If user uses other language, reply in English.
- DO NOT say "Based on my knowledge", "I think", or invent details.

DATABASE INFORMATION (ONLY source):
----------
{context}
----------

Conversation history (last few turns for context):
{str(history[-4:]) if history and len(history) >= 4 else str(history)}
"""

    def build_conversational_query(self, history: List[dict], current_prompt: str) -> str:
        """Build query with recent conversation context."""
        query_parts = [current_prompt]
        
        if len(history) >= 2:
            last_exchange = history[-2:]
            for msg in last_exchange:
                if msg["role"] == "user":
                    query_parts.append(f"Previous question: {msg['content']}")
                elif msg["role"] == "assistant":
                    query_parts.append(f"Previous context: {msg['content']}")
        return " ".join(query_parts)

    def extract_main_topic(self, prompt: str, history: List[dict]) -> str:
        """Extract main topic, detecting follow-up questions."""
        if len(history) < 2:
            return prompt
        
        last_student_messages = [msg for msg in history[-2:] if msg["role"] == "user"]
        if not last_student_messages:
            return prompt
        
        last_student_prompt = last_student_messages[-1]["content"]
        if self.is_follow_up_question(prompt, last_student_prompt):
            print(f"Detected follow-up question")
            return f"{last_student_prompt} {prompt}"
        
        return prompt

    def process_prompt(self, request: PromptRequest) -> PromptResponse:
        """Process user prompt and return response."""
        prompt = request.prompt
        conversation_session = request.conversationSession

        print(f"\n{'='*60}")
        print(f"[SESSION] {conversation_session}")
        print(f"[USER] {prompt}")

        intent = self.detect_intent(prompt)
        print(f"[INTENT] {intent}")

        if not self.session_manager.session_exists(conversation_session):
            self.session_manager.create_session(conversation_session, request.username)

        history = self.session_manager.get_session_history(conversation_session)
        print(f"[HISTORY] Retrieved {len(history)} messages")

        main_topic = self.extract_main_topic(prompt, history)
        conversational_query = self.build_conversational_query(history, main_topic)

        program_id = self._extract_program_from_query(prompt)
        
        # Build where filter to only search current (non-archived) documents
        where_filter = {"is_archived": False}
        if program_id:
            # Combine program filter with archive filter
            where_filter = {
                "$and": [
                    {"is_archived": False},
                    {"program_id": program_id}
                ]
            }
        
        print(f"[QUERY FILTER] Searching only current documents (is_archived=False)")

        try:
            collection = self.get_collection()
            results = collection.query(
                query_texts=[conversational_query],
                n_results=10,
                where=where_filter
            )
            
            num_results = len(results['documents'][0]) if results['documents'] else 0
            print(f"[CHROMADB] Retrieved {num_results} documents")
            
            if results['metadatas'] and results['metadatas'][0]:
                print(f"[METADATA] Sample archive status: is_archived={results['metadatas'][0][0].get('is_archived', 'N/A')}")
        except Exception as e:
            print(f"[ERROR] ChromaDB query failed: {e}")
            results = {'documents': [[]], 'metadatas': [[]]}

        context = self._extract_context_from_results(results)
        context_length = len(context.strip()) if context else 0
        print(f"[CONTEXT] Retrieved {context_length} characters")

        if not context.strip():
            print(f"[NO CONTEXT] No matching documents found")
            ai_response = "I'm sorry, but I don't have information about that topic in our current records."
            self._update_conversation_history(conversation_session, history, prompt, ai_response)
            
            return PromptResponse(
                success=True,
                response=ai_response,
                requires_auth=False,
                intent=intent
            )

        system_prompt = self._create_system_prompt_strict(context, history)
        messages = self._prepare_messages(system_prompt, history, prompt)

        print(f"[GPT INPUT] {len(messages)} messages")

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,
            max_tokens=500,
            top_p=0.9
        )

        ai_response = response.choices[0].message.content
        print(f"[AI RESPONSE] {ai_response[:150]}...")

        self._update_conversation_history(conversation_session, history, prompt, ai_response)
        print(f"[HISTORY UPDATED] {len(history) + 2} messages in session")

        return PromptResponse(
            success=True,
            response=ai_response,
            requires_auth=False,
            intent=intent
        )

    def _extract_context_from_results(self, results) -> str:
        """Extract text context from ChromaDB query results."""
        context_parts = []
        
        if results['documents'] and len(results['documents']) > 0:
            docs_list = results['documents'][0] if isinstance(results['documents'][0], list) else results['documents']
            for doc in docs_list[:10]:
                if isinstance(doc, str) and doc and doc.strip():
                    context_parts.append(doc)
        
        return "\n".join(context_parts)

    def _prepare_messages(self, system_prompt: str, history: List[dict], prompt: str) -> List[dict]:
        """Prepare messages for OpenAI API."""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": prompt})
        return messages

    def _update_conversation_history(self, session_id: str, history: List[dict],
                                    prompt: str, ai_response: str) -> None:
        """Update conversation history for specific session."""
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": ai_response})
        trimmed = history[-8:]
        self.session_manager.update_history(session_id, trimmed)
        print(f"[HISTORY] Saved {len(trimmed)} messages")

    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs."""
        return self.session_manager.get_all_sessions()


app = FastAPI()
vfd = VirtualFrontDesk()


@app.post("/student/login", response_model=LoginResponse)
async def student_login(request: LoginRequest):
    try:
        print(f"Attempting login for student: {request.username}")
        return LoginResponse(success=True, message="Login successful")
    except Exception as e:
        print(f"Login error: {str(e)}")
        return LoginResponse(success=False, message="Login error", error=str(e))


@app.post("/VirtualFrontDesk", response_model=PromptResponse)
async def ask_question(request: PromptRequest):
    return vfd.process_prompt(request)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "ChatMate API is running"}


@app.get("/sessions")
async def get_sessions():
    sessions = vfd.get_all_sessions()
    return {"sessions": sessions, "total": len(sessions)}


@app.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Get metadata for a specific session."""
    metadata = vfd.session_manager.get_session_metadata(session_id)
    if not metadata:
        return {"error": "Session not found"}
    return metadata


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session."""
    if vfd.session_manager.delete_session(session_id):
        return {"success": True, "message": f"Session {session_id} deleted"}
    return {"success": False, "message": "Session not found"}


def start_database_sync():
    """Start the database synchronization service in a separate thread."""
    from KnowledgeRepository import KnowledgeRepository
    synchronizer = KnowledgeRepository()
    synchronizer.run_continuous_sync()


def start_fastapi_server():
    """Start the FastAPI server."""
    uvicorn.run("VirtualFrontDesk:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    print("Starting ChatMate Application...")
    print("=" * 50)
    
    sync_thread = threading.Thread(target=start_database_sync, daemon=True)
    sync_thread.start()
    
    time.sleep(2)
    
    print("\nStarting FastAPI server...")
    start_fastapi_server()