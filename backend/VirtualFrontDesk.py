import time
import uvicorn
import requests
import threading
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List, Optional
from AuthDetector import AuthDetector
from bs4 import BeautifulSoup


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
    
    def __init__(self,):
        super().__init__()
        self.conversation_history: Dict[str, List[dict]] = {}
        self.user_sessions: Dict[str, requests.Session] = {}
      
    def store_student_session(self, username: str, session: requests.Session) -> None:
        self.user_sessions[username] = session
        print(f"Stored session for user: {username}")
        
    def get_user_session(self, username: str) -> Optional[requests.Session]:
        return self.user_sessions.get(username)
    
    def is_user_authenticated(self, username: str) -> bool:
        return username in self.user_sessions
    
    def get_session_history(self, session_id: str) -> List[dict]:
        return self.conversation_history.get(session_id, [])
    
    def update_session_history(self, session_id: str, history: List[dict]) -> None:
        self.conversation_history[session_id] = history
        
    def get_all_sessions(self) -> List[str]:
        return list(self.conversation_history.keys())
    
    def build_conversational_query(self, history: List[dict], current_prompt: str) -> str:
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
        More flexible matching for natural language queries.
        """
        prompt_lower = prompt.lower()
        
        # Map of programs and their detection keywords
        # Order matters - more specific patterns first to avoid conflicts
        program_keywords = {
            'bsba_om': ['operations management', 'bsba om', 'bsba-om', 'om student', 'om program'],
            'bsba_fm': ['financial management', 'bsba fm', 'bsba-fm', 'fm student', 'fm program'],
            'bsba_mm': ['marketing management', 'bsba mm', 'bsba-mm', 'mm student', 'mm program'],
            'bsentrep': ['entrepreneurship', 'bsentrep', 'bs entrep', 'entrep student', 'entrep program'],
            'bsit': ['bsit', 'information technology', 'it student', 'it program', 'bs in it'],
            'bsed_math': [
                'bsed math',
                'bsed-math',
                'secondary education math',
                'mathematics teacher',
                'math education',
                'education mathematics',
                'math secondary'
            ],
            'bsed_english': [
                'bsed english',
                'bsed-eng',
                'secondary education english',
                'english teacher',
                'english education',
                'education english',
                'english secondary'
            ],
            'beed': [
                'beed',
                'elementary education',
                'elementary teacher',
                'primary education',
                'grade school teacher'
            ],
            'act_network': [
                'networking',
                'act network',
                'act-network',
                'network track',
                'data communications and networking'
            ],
            'act_data': [
                'data engineering',
                'act data',
                'act-data',
                'data track',
                'data management'
            ],
            'act_appdev': [
                'applications development',
                'act app',
                'act application',
                'appdev track',
                'application development'
            ],
            'tcp': ['teacher certificate', 'tcp', 'teacher certificate program'],
        }
        
        # Check for exact program mentions first
        for program_id, keywords in program_keywords.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    print(f"📌 Detected program context: {program_id} (keyword: '{keyword}')")
                    return program_id
        
        # If no program explicitly mentioned, return None
        # This allows general queries to work without program filtering
        return None
    
    def process_prompt(self, request: PromptRequest) -> PromptResponse:
        print(f"Processing prompt: '{request.prompt}'")
        prompt = request.prompt
        conversation_session = request.conversationSession
        username = request.username  
        
        intent, similarities = self.detect_intent(prompt)
        requires_auth = self.requires_authentication(intent)
        
        print(f"Detected intent: {intent}, Requires Auth: {requires_auth}")
        print(f"Intent similarities: {similarities}")
        
        if requires_auth:
            if username and self.is_user_authenticated(username):
                print(f"User {username} is authenticated, processing private data request for {intent}")
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

                history = self.get_session_history(conversation_session)
                system_prompt = self._create_system_prompt(private_data, history)
                messages = self._prepare_messages(system_prompt, history, prompt)
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages
                )
                ai_response = response.choices[0].message.content
                print(f"AI Response with private data: {ai_response}")
                self._update_conversation_history(conversation_session, history, prompt, ai_response)
                
                return PromptResponse(
                    success=True, 
                    response=ai_response, 
                    requires_auth=False, 
                    intent=intent
                )
            
            else:
                print(f"Authentication required for intent: {intent}")
                return PromptResponse(
                    success=True, 
                    response="Please log in to access your private information.", 
                    requires_auth=True, 
                    intent=intent
                )

        print(f"Processing general query with intent: {intent}")
            
        history = self.get_session_history(conversation_session)
        enhanced_query = self.extract_main_topic(prompt, history)
        conversational_query = self.build_conversational_query(history, enhanced_query)
        
        # Detect if user wants archived/historical data
        from VersionDetector import VersionDetector
        version_detector = VersionDetector()
        archive_settings = version_detector.should_include_archived(prompt)
        
        # STRICT DEFAULT: Only current documents unless explicitly requested
        where_filter = {"is_archived": False}
        search_mode = "CURRENT ONLY"
        archive_filter_value = False
        
        if archive_settings['include_archived']:
            if archive_settings['archived_only']:
                where_filter = {"is_archived": True}
                search_mode = "ARCHIVED ONLY"
                archive_filter_value = True
            else:
                where_filter = None  # Include both
                search_mode = "CURRENT + ARCHIVED"
                archive_filter_value = None
        
        # CRITICAL: Extract program context from query for course documents
        program_id = self._extract_program_from_query(prompt)
        
        # Build dynamic where_filter to include program filtering
        if program_id:
            # When program is detected
            if archive_filter_value is None:
                # Include both archived and current for this program
                where_filter = {"program_id": program_id}
                search_mode += f" | PROGRAM: {program_id}"
            else:
                # Combine filters: is_archived AND program_id
                where_filter = {
                    "$and": [
                        {"is_archived": archive_filter_value},
                        {"program_id": program_id}
                    ]
                }
                search_mode += f" | PROGRAM: {program_id}"
        else:
            # No program detected - use archive filter only
            # This allows general questions to work
            if where_filter is None:
                where_filter = None  # No filter, get all
            # else: where_filter is already {"is_archived": False}
        
        print(f"🔍 Search Mode: {search_mode}")
        if where_filter:
            print(f"📋 Filter: {where_filter}")
        else:
            print(f"📋 Filter: None (all documents)")
        
        # Query with strict filtering
        query_params = {
            "query_texts": [conversational_query],
            "n_results": 100
        }
        if where_filter:
            query_params["where"] = where_filter
        
        results = self.get_collection(force_refresh=True).query(**query_params)
        
        # Debug: Show what we got
        if results['metadatas'] and results['metadatas'][0]:
            print(f"📊 Retrieved {len(results['metadatas'][0])} results")
            archived_count = sum(1 for m in results['metadatas'][0] if m.get('is_archived', False))
            current_count = len(results['metadatas'][0]) - archived_count
            print(f"   Archived: {archived_count} | Current: {current_count}")
            
            if program_id:
                program_matches = sum(1 for m in results['metadatas'][0] if m.get('program_id') == program_id)
                print(f"   Program '{program_id}' matches: {program_matches}")
            
            # Show sample of what was retrieved
            if results['metadatas'][0]:
                print(f"   Sample metadata from result:")
                sample_meta = results['metadatas'][0][0] if results['metadatas'][0] else {}
                print(f"     - program_id: {sample_meta.get('program_id', 'N/A')}")
                print(f"     - data_type: {sample_meta.get('data_type', 'N/A')}")
                print(f"     - is_archived: {sample_meta.get('is_archived', 'N/A')}")
        
        context = self._extract_context_from_results(results)
        
        if not context.strip():
            ai_response = "I'm sorry, but I don't have information about that topic in our current records. Please try asking about general school information, programs, or fees."
            print(f"No relevant context found for query")
            self._update_conversation_history(conversation_session, history, prompt, ai_response)
            
            return PromptResponse(
                success=True,
                response=ai_response,
                requires_auth=False,
                intent=intent
            )
        
        system_prompt = self._create_system_prompt(context, history)
        messages = self._prepare_messages(system_prompt, history, prompt)
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        ai_response = response.choices[0].message.content
        print(f"AI Response: {ai_response[:100]}...")
        
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
            # results['documents'] is a list of lists (one list per query)
            docs_list = results['documents'][0] if isinstance(results['documents'][0], list) else results['documents']
            for doc in docs_list[:10]:
                if isinstance(doc, str) and doc and doc.strip():
                    context_parts.append(doc)
        
        return "\n".join(context_parts)
    
    def _create_system_prompt(self, context: str, history: List[dict] = None) -> str:
        if history is None:
            history = []
        
        return f"""You are TLC Chatmate, a helpful AI assistant for The Lewis College.

        INSTRUCTIONS:
        - Answer based ONLY on the provided information.
        - Be accurate and concise.
        - If information is not available, say so directly.
        - Do NOT make up or assume information.
        - Keep responses friendly and professional.

        RESPONSE GUIDELINES:
        - Provide direct, accurate answers.
        - Use 2-3 sentences maximum for simple questions.
        - For complex topics, organize information clearly.
        - If clarification is needed, ask ONE specific question.

        CLARIFICATION FORMAT:
        - State what you can help with briefly (optional, 1 short phrase)
        - Ask the clarification question directly
        - Provide specific options or examples if applicable

        If the question is clear, do NOT ask follow-up questions.

        WHEN TO USE BULLET LISTS (REQUIRED):
        - Enrollment requirements
        - Scholarships
        - School fees
        - Any checklist-style or multi-item information

        WHEN NOT TO USE BULLETS:
        - Single facts (founder, start of classes, tuition only)
        - Short informational answers

        FAIL-SAFE:
        If information is not available:
        - Do NOT use conversational introduction
        - Do NOT use closing line
        - Politely state that the information is not available in a single sentence
        - Do NOT guess or fabricate

        CORRECT FORMAT WHEN INFO NOT AVAILABLE:
        - "I'm sorry, but [specific information] is not available in our current records."

        RESPONSE STRUCTURE:
        1. Short conversational introduction (1 sentence)
        2. Correctly formatted information (paragraph or list)
        3. Optional polite closing line (1 sentence only)

        LANGUAGE RULES:
        - Respond only in English, Tagalog, or Bicol
        - If another language is used, reply in English and state the language limitation

        TERMINOLOGY:
        - "Course" refers to subjects
        - "Program" refers to degree or academic programs

        GREETINGS & CLOSING:
        - If greeted, greet back and ask how you may help
        - If the student ends politely, respond with a professional closing
        - Do NOT extend conversation unnecessarily

        ----------
        data:
        {str(history[-4:]) if history and len(history) >= 4 else str(history)}
        {context}
        """

        
    def _prepare_messages(self, system_prompt: str, history: List[dict], prompt: str) -> List[dict]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-6:])
        messages.append({"role": "user", "content": prompt})
        
        return messages
        
    def _update_conversation_history(self, session_id: str, history: List[dict], prompt: str, ai_response: str) -> None:
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": ai_response})
        self.update_session_history(session_id, history[-4:])
        
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
                return LoginResponse( success=True, message="Login successful")
        
        print(f"Login failed for student: {request.username}")
        return LoginResponse( success=False, message="Login failed", error="Invalid credentials or login failed")
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        return LoginResponse( success=False, message="Login error", error=str(e))
        
@app.post("/VirtualFrontDesk", response_model=PromptResponse)
async def ask_question(request: PromptRequest):
    return vfd.process_prompt(request)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "ChatMate API is running"}

@app.get("/sessions")
async def get_sessions():
    return {"sessions": vfd.get_all_sessions()}


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
    
    # Start database sync in a separate thread
    sync_thread = threading.Thread(target=start_database_sync, daemon=True)
    sync_thread.start()
    
    # Give the sync service a moment to start
    time.sleep(2)
    
    # Start the FastAPI server (this will block)
    print("\nStarting FastAPI server...")
    start_fastapi_server()