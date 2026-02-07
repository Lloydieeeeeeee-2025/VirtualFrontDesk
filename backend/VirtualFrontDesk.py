
import time
import uvicorn
import requests
import threading
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List, Optional
from AuthDetector import AuthDetector
from SessionManager import SessionManager
from bs4 import BeautifulSoup
import pytz
from datetime import datetime


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
    

class VirtualFrontDesk(AuthDetector):
    
    def __init__(self):
        super().__init__()
        self.session_manager = SessionManager(max_history_per_session=4)
        self.user_sessions: Dict[str, requests.Session] = {}
        
    def store_student_session(self, username: str, session: requests.Session) -> None:
        """Store authenticated user session."""
        self.user_sessions[username] = session
        print(f"Stored session for user: {username}")
        
    def get_user_session(self, username: str) -> Optional[requests.Session]:
        """Retrieve authenticated user session."""
        return self.user_sessions.get(username)
    
    def is_user_authenticated(self, username: str) -> bool:
        """Check if user is authenticated."""
        return username in self.user_sessions
    
    def get_session_history(self, session_id: str) -> List[dict]:
        """Get conversation history for a session."""
        return self.session_manager.get_session_history(session_id)
    
    def update_session_history(self, session_id: str, history: List[dict]) -> None:
        """Update conversation history for a session."""
        self.session_manager.update_history(session_id, history)
        
    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs."""
        return self.session_manager.get_all_sessions()
    
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
            print(f"Detected follow-up question: '{prompt}' is related to '{last_student_prompt}'")
            return f"{last_student_prompt} {prompt}"
        
        return prompt
    
    def _extract_program_from_query(self, prompt: str) -> Optional[str]:
        """
        Extract program identifier from user query.
        Returns program_id like 'bsit', 'bsba_om', 'bsed_math', etc., or None.
        """
        prompt_lower = prompt.lower()
        
        program_keywords = {
            'bsba_om': ['operations management', 'bsba om', 'bsba-om', 'om student', 'om program'],
            'bsba_fm': ['financial management', 'bsba fm', 'bsba-fm', 'fm student', 'fm program'],
            'bsba_mm': ['marketing management', 'bsba mm', 'bsba-mm', 'mm student', 'mm program'],
            'bsentrep': ['entrepreneurship', 'bsentrep', 'bs entrep', 'entrep student', 'entrep program'],
            'bsit': ['bsit', 'information technology', 'it student', 'it program', 'bs in it'],
            'bsed_math': [
                'bsed math', 'bsed-math', 'secondary education math',
                'mathematics teacher', 'math education', 'education mathematics', 'math secondary'
            ],
            'bsed_english': [
                'bsed english', 'bsed-eng', 'secondary education english',
                'english teacher', 'english education', 'education english', 'english secondary'
            ],
            'beed': [
                'beed', 'elementary education', 'elementary teacher',
                'primary education', 'grade school teacher'
            ],
            'act_network': [
                'networking', 'act network', 'act-network', 'network track',
                'data communications and networking'
            ],
            'act_data': [
                'data engineering', 'act data', 'act-data', 'data track', 'data management'
            ],
            'act_appdev': [
                'applications development', 'act app', 'act application',
                'appdev track', 'application development'
            ],
            'tcp': ['teacher certificate', 'tcp', 'teacher certificate program'],
        }
        
        for program_id, keywords in program_keywords.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    print(f"📌 Detected program context: {program_id}")
                    return program_id
        
        return None
    
    def _create_system_prompt_strict(self, context: str, history: List[dict] = None) -> str:
        """Create STRICT system prompt for GPT-4o with dynamic greetings, purpose, and conduct rules."""
        if history is None:
            history = []

        # Get current time in Philippines
        ph_time = datetime.now(pytz.timezone("Asia/Manila"))
        hour = ph_time.hour
        if 5 <= hour < 12:
            greeting = "Good morning"
        elif 12 <= hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        return f"""You are TLC ChatMate, the official virtual front desk of The Lewis College.

📌 PURPOSE: Provide immediate, accurate academic and administrative assistance using only verified college documents—reducing manual inquiry load.

{greeting}! I'm here to help with your questions about enrollment, programs, policies, and services at The Lewis College.

CRITICAL INSTRUCTIONS - MUST FOLLOW:
1. Answer ONLY using the provided database information below.
2. Do NOT use general knowledge, assumptions, or external facts.
3. If exact info isn't in the database, say: "I'm sorry, but I don't have information about [topic] in our current records."
4. For greetings → respond warmly with "{greeting}!" once, then assist.
5. For farewells/compliments (e.g., "thank you", "good job") → reply politely and end conversation (e.g., "You're welcome! Have a great day.").
6. If user uses verbal misconduct, disruptive behavior, aggression, harassment, profanity, vulgar/obscene/offensive/inappropriate language:
   - Stay calm, neutral, and professional.
   - Do NOT react emotionally, sarcastically, or defensively.
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

Remember: You are TLC ChatMate — helpful, precise, and strictly factual. If it's not in the database above, you don't know it.
"""

    def process_prompt(self, request: PromptRequest) -> PromptResponse:
        """Process user prompt with isolated session history."""
        print(f"\n{'='*60}")
        print(f"[NEW PROMPT] Session: {request.conversationSession}")
        print(f"[PROMPT] {request.prompt}")
        print(f"{'='*60}")
        
        prompt = request.prompt
        conversation_session = request.conversationSession
        username = request.username
        
        # CRITICAL FIX #1: Always start with FRESH session
        # Verify session exists, if not create it fresh
        if not self.session_manager.session_exists(conversation_session):
            print(f"⚠ Session does not exist, creating new: {conversation_session}")
            self.session_manager.create_session(
                session_id=conversation_session,
                user_id=username
            )
        
        # Get ISOLATED history for THIS session only
        history = self.get_session_history(conversation_session)
        print(f"[HISTORY] Retrieved {len(history)} messages for this session")
        self.session_manager.debug_session_state(conversation_session)
        
        intent, similarities = self.detect_intent(prompt)
        requires_auth = self.requires_authentication(intent)
        
        print(f"[INTENT] {intent}, Auth Required: {requires_auth}")
        
        if requires_auth:
            if username and self.is_user_authenticated(username):
                print(f"[AUTH] User {username} authenticated, processing private data")
                self.session = self.get_user_session(username)
                url = self.urls.get(intent)
                if not url:
                    return PromptResponse(
                        success=False, 
                        response="Unable to retrieve the requested information.",
                        requires_auth=False,
                        intent=intent
                    )

                private_data = self.extract_data(url, intent)
                if private_data is None:
                    return PromptResponse(
                        success=True, 
                        response="Session expired or unable to access your data. Please log in again.",
                        requires_auth=True,
                        intent=intent
                    )

                system_prompt = self._create_system_prompt(private_data, history)
                messages = self._prepare_messages(system_prompt, history, prompt)
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500
                )

                ai_response = response.choices[0].message.content
                print(f"[AI RESPONSE] {ai_response[:100]}...")
                
                self._update_conversation_history(conversation_session, history, prompt, ai_response)
                return PromptResponse(
                    success=True,
                    response=ai_response,
                    requires_auth=False,
                    intent=intent
                )
            else:
                print(f"[AUTH FAILED] User not authenticated")
                return PromptResponse(
                    success=False,
                    response="This information requires login.",
                    requires_auth=True,
                    intent=intent
                )
        
        # CRITICAL FIX #2: Public query - STRICT context checking
        print(f"[QUERY TYPE] Public query - checking database")
        
        from VersionDetector import VersionDetector
        version_detector = VersionDetector()
        archive_settings = version_detector.should_include_archived(prompt)
        
        # STRICT: Only current documents unless explicitly requested
        where_filter = {"is_archived": False}
        search_mode = "CURRENT ONLY"
        
        if archive_settings['include_archived']:
            if archive_settings['archived_only']:
                where_filter = {"is_archived": True}
                search_mode = "ARCHIVED ONLY"
            else:
                where_filter = None  # Include both
                search_mode = "CURRENT + ARCHIVED"
        
        # Extract program context
        program_id = self._extract_program_from_query(prompt)
        
        # Build where_filter
        if program_id:
            if where_filter is None:
                where_filter = {"program_id": program_id}
            else:
                where_filter = {
                    "$and": [
                        where_filter,
                        {"program_id": program_id}
                    ]
                }
            search_mode += f" | PROGRAM: {program_id}"
        
        print(f"[SEARCH MODE] {search_mode}")
        print(f"[WHERE FILTER] {where_filter}")
        
        # Query ChromaDB
        try:
            collection = self.get_collection()
            results = collection.query(
                query_texts=[prompt],
                n_results=10,
                where=where_filter if where_filter else None
            )
            
            num_results = len(results['documents'][0]) if results['documents'] else 0
            print(f"[CHROMADB] Retrieved {num_results} documents")
            
            if num_results > 0 and results['metadatas']:
                print(f"[METADATA] Sample: {results['metadatas'][0][0] if results['metadatas'][0] else 'None'}")
        except Exception as e:
            print(f"[ERROR] ChromaDB query failed: {e}")
            results = {'documents': [[]], 'metadatas': [[]]}
        
        # CRITICAL FIX #3: Extract context with logging
        context = self._extract_context_from_results(results)
        context_length = len(context.strip()) if context else 0
        print(f"[CONTEXT] Retrieved {context_length} characters")
        
        # CRITICAL FIX #4: STRICT check - if no context, MUST return "not available"
        if not context.strip():
            print(f"[NO CONTEXT] No matching documents found - GPT will NOT generate answer")
            ai_response = "I'm sorry, but I don't have information about that topic in our current records."
            print(f"[AI RESPONSE] {ai_response}")
            self._update_conversation_history(conversation_session, history, prompt, ai_response)
            
            return PromptResponse(
                success=True,
                response=ai_response,
                requires_auth=False,
                intent=intent
            )
        
        # Create STRICT system prompt that enforces database-only answers
        system_prompt = self._create_system_prompt_strict(context, history)
        messages = self._prepare_messages(system_prompt, history, prompt)
        
        print(f"[GPT INPUT] {len(messages)} messages, system prompt length: {len(system_prompt)}")
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.5,  # Lower temperature for stricter adherence
            max_tokens=500,
            top_p=0.9
        )
        
        ai_response = response.choices[0].message.content
        print(f"[AI RESPONSE] {ai_response[:150]}...")
        
        # Update ONLY this session's history
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
    
    def _create_system_prompt(self, context: str, history: List[dict] = None) -> str:
        """Legacy system prompt for authenticated data."""
        if history is None:
            history = []
        
        return f"""You are TLC Chatmate, a helpful AI assistant for The Lewis College.

INSTRUCTIONS:
- Answer based ONLY on the provided information.
- Be accurate and concise.
- If information is not available, say so directly.
- Do NOT make up or assume information.

----------
data:
{context}
{str(history[-4:]) if history and len(history) >= 4 else str(history)}
"""
    
    def _prepare_messages(self, system_prompt: str, history: List[dict], prompt: str) -> List[dict]:
        """Prepare messages for OpenAI API."""
        messages = [{"role": "system", "content": system_prompt}]
        # Include up to last 4 messages (2 exchanges) for context
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": prompt})
        
        return messages
        
    def _update_conversation_history(self, session_id: str, history: List[dict], prompt: str, ai_response: str) -> None:
        """Update conversation history for specific session."""
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": ai_response})
        # Keep only last 4 exchanges (8 messages) per session
        trimmed = history[-8:]
        self.session_manager.update_history(session_id, trimmed)
        print(f"[HISTORY] Saved {len(trimmed)} messages")


app = FastAPI()
vfd = VirtualFrontDesk()   


@app.post("/student/login", response_model=LoginResponse)
async def student_login(request: LoginRequest):
    try:
        print(f"Attempting login for student: {request.username}")
        session = vfd.login_with_selenium(request.username, request.password)
        
        if session:
            vfd.store_student_session(request.username, session)
            test_response = session.get(vfd.urls['schedule'])
            if "login" not in test_response.url:
                print(f"Login successful for student: {request.username}")
                return LoginResponse(success=True, message="Login successful")
        
        print(f"Login failed for student: {request.username}")
        return LoginResponse(success=False, message="Login failed", error="Invalid credentials")
        
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