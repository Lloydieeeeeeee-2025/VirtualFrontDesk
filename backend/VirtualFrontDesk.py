import time
import uvicorn
import threading
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional
from SessionManager import SessionManager
from ChromaDBService import ChromaDBService
from KnowledgeRepository import KnowledgeRepository
import pytz
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv


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

        self.closing_keywords = ['okay', 'ok', 'thanks', 'thank you', 'bye', 'goodbye', 'see you', 'done']

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

    def _is_initial_conversation(self, history: List[dict]) -> bool:
        """Check if this is the initial conversation (first message)."""
        return len(history) == 0

    def _is_closing_message(self, prompt: str) -> bool:
        """Check if user message contains closing keywords."""
        prompt_lower = prompt.lower().strip()
        return any(keyword in prompt_lower for keyword in self.closing_keywords)

    def _extract_program_from_query(self, prompt: str) -> Optional[str]:
        """Extract program identifier from user query."""
        prompt_lower = prompt.lower()
        
        for program_id, keywords in self.program_keywords.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    return program_id
        
        return None

    def _get_greeting(self) -> str:
        """Get appropriate greeting based on current time in Manila."""
        ph_time = datetime.now(pytz.timezone("Asia/Manila"))
        hour = ph_time.hour
        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 18:
            return "Good afternoon"
        else:
            return "Good evening"

    def _create_system_prompt_strict(self, context: str, history: List[dict], is_initial: bool) -> str:
        """Create STRICT system prompt for GPT-4o."""
        greeting_text = ""
        if is_initial:
            greeting = self._get_greeting()
            greeting_text = f"{greeting}! I'm here to help with your questions about enrollment, programs, policies, and services at The Lewis College.\n\n"

        return f"""You are TLC ChatMate, the official virtual front desk of The Lewis College.

PURPOSE: Provide immediate, accurate academic and administrative assistance using only verified college documents.

{greeting_text}CRITICAL INSTRUCTIONS - MUST FOLLOW:
1. Answer ONLY using the provided database information below.
2. Do NOT use general knowledge, assumptions, or external facts.
3. If exact info isn't in the database, say: "I'm sorry, but I don't have information about [topic] in our current records."
4. For greetings → respond warmly once only in the initial message.
5. For farewells → reply politely with a closing message and end conversation.
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
            return f"{last_student_prompt} {prompt}"
        
        return prompt

    def process_prompt(self, request: PromptRequest) -> PromptResponse:
        """Process user prompt and return response."""
        prompt = request.prompt
        conversation_session = request.conversationSession

        intent = self.detect_intent(prompt)

        if not self.session_manager.session_exists(conversation_session):
            self.session_manager.create_session(conversation_session, request.username)

        history = self.session_manager.get_session_history(conversation_session)
        is_initial = self._is_initial_conversation(history)

        # Handle closing message
        if self._is_closing_message(prompt):
            closing_response = "Thank you for reaching out! Is there anything else I can help you with today?"
            self._update_conversation_history(conversation_session, history, prompt, closing_response)
            return PromptResponse(
                success=True,
                response=closing_response,
                requires_auth=False,
                intent=intent
            )

        main_topic = self.extract_main_topic(prompt, history)
        conversational_query = self.build_conversational_query(history, main_topic)

        program_id = self._extract_program_from_query(prompt)
        
        # Build where filter to only search current (non-archived) documents
        where_filter = {"is_archived": False}
        if program_id:
            where_filter = {
                "$and": [
                    {"is_archived": False},
                    {"program_id": program_id}
                ]
            }

        try:
            collection = self.get_collection()
            results = collection.query(
                query_texts=[conversational_query],
                n_results=10,
                where=where_filter
            )
        except Exception as e:
            print(f"ChromaDB query failed: {e}")
            results = {'documents': [[]], 'metadatas': [[]]}

        context = self._extract_context_from_results(results)

        if not context.strip():
            ai_response = "I'm sorry, but I don't have information about that topic in our current records."
            self._update_conversation_history(conversation_session, history, prompt, ai_response)
            
            return PromptResponse(
                success=True,
                response=ai_response,
                requires_auth=False,
                intent=intent
            )

        system_prompt = self._create_system_prompt_strict(context, history, is_initial)
        messages = self._prepare_messages(system_prompt, history, prompt)

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,
            max_tokens=500,
            top_p=0.9
        )

        ai_response = response.choices[0].message.content

        self._update_conversation_history(conversation_session, history, prompt, ai_response)

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

    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs."""
        return self.session_manager.get_all_sessions()


app = FastAPI()
vfd = VirtualFrontDesk()
knowledge_repo = KnowledgeRepository()


@app.on_event("startup")
async def startup_event():
    """Run initial sync on startup."""
    def initial_sync():
        knowledge_repo.sync_data_to_chromadb()
    
    sync_thread = threading.Thread(target=initial_sync, daemon=True)
    sync_thread.start()


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


@app.get("/admin/sync-status")
async def get_sync_status():
    """Get the current synchronization status."""
    return knowledge_repo.get_progress()


@app.post("/admin/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """Trigger a manual synchronization."""
    if knowledge_repo.progress["status"] == "running":
         return {"success": False, "message": "Sync already in progress"}
    
    background_tasks.add_task(knowledge_repo.sync_data_to_chromadb)
    return {"success": True, "message": "Sync started"}


@app.get("/admin/check-updates")
async def check_updates():
    """Check if updates are available."""
    has_updates = knowledge_repo.check_updates_available()
    return {"updates_available": has_updates}


def start_fastapi_server():
    """Start the FastAPI server."""
    uvicorn.run("VirtualFrontDesk:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    print("Starting ChatMate Application...")
    print("=" * 50)
    
    print("\nStarting FastAPI server...")
    start_fastapi_server()