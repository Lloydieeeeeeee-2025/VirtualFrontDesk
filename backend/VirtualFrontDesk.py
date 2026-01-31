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
    username: Optional[str] = None # october 18
    
class PromptResponse(BaseModel):
    success: bool
    response: str
    requires_auth: bool = False
    intent: Optional[str] = None
    
class VirtualFrontDesk(AuthDetector):
    
    def __init__(self,):
        super().__init__()
        self.conversation_history: Dict[str, List[dict]] = {}
        self.user_sessions: Dict[str, requests.Session] = {} # October 18
      
    # october 18 - sa pag scrape sa portal
    def store_student_session(self, username: str, session: requests.Session) -> None:
        self.user_sessions[username] = session
        print(f"Stored session for user: {username}")
        
    def get_user_session(self, username: str) -> Optional[requests.Session]:
        return self.user_sessions.get(username)
    
    def is_user_authenticated(self, username: str) -> bool:
        return username in self.user_sessions
    # end 
    
    # gamit sa session memory para sa conversation ellipsis or clarification   
    def get_session_history(self, session_id: str) -> List[dict]:
        return self.conversation_history.get(session_id, [])
    
    def update_session_history(self, session_id: str, history: List[dict]) -> None:
        self.conversation_history[session_id] = history
        
    def get_all_sessions(self) -> List[str]:
        return list(self.conversation_history.keys())
    # end of conversation ellipsis
    
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
                    model="gpt-5-mini",
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
        
        if archive_settings['include_archived']:
            if archive_settings['archived_only']:
                where_filter = {"is_archived": True}
                search_mode = "ARCHIVED ONLY"
            else:
                where_filter = None  # Include both
                search_mode = "CURRENT + ARCHIVED"
        
        print(f"🔍 Search Mode: {search_mode}")
        
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
            print(f"   Current: {current_count}, Archived: {archived_count}")
        
        context_parts = []
        relevant_count = 0
        SIMILARITY_THRESHOLD = 0.3
        
        if results['documents'] and results['distances']:
            for doc, meta, distance in zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            ):
                similarity = 1 / (1 + distance)
                
                if similarity >= SIMILARITY_THRESHOLD and doc and len(doc.strip()) > 10:
                    relevant_count += 1
                    
                    # Tag archived content clearly
                    if meta.get('is_archived', False):
                        version_tag = f"[ARCHIVED {meta.get('revision_year', 'VERSION')}]"
                        context_parts.append(f"{version_tag} {doc}")
                    else:
                        context_parts.append(doc)
        
        if not context_parts:
            context = "NO_RELEVANT_DATA"
            print(f"⚠ No relevant results found for query: '{prompt}'")
        else:
            context = "\n\n".join(context_parts)
            print(f"✓ Found {relevant_count} relevant documents")
        
        system_prompt = self._create_system_prompt(context, history)
        messages = self._prepare_messages(system_prompt, history, prompt)
        response = self.openai_client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages
        )
        ai_response = response.choices[0].message.content
        print(f"AI Response: {ai_response}")
        
        self._update_conversation_history(conversation_session, history, prompt, ai_response)
        return PromptResponse(
            success=True, 
            response=ai_response, 
            requires_auth=False, 
            intent=intent
        )
        
    def _create_system_prompt(self, context: str, history: List[dict]) -> str:
        if context == "NO_RELEVANT_DATA":
            return """You are a professional, conversational, and student-friendly assistant.

            CRITICAL INSTRUCTION:
            • If you don't have enough information to answer, politely say you don't have the details at the moment.
            • Encourage the student to provide more details or to contact the office for accurate information.
            • If the question is unclear, kindly ask for clarification before answering.
            • Always sound natural and human — never mention any system, database, or stored records.
            • Avoid robotic or repetitive tone.

            Example (do not copy exactly):
            → "I'm sorry, I don't have specific details about that right now. Could you please share a bit more about what you need, or you may reach out to the office for assistance."

            DO NOT:
            • Mention any technical terms like system, data, or database.
            • Guess or assume missing information.
            • Provide unrelated or generic educational info.
            """

        return f"""
            You are a friendly and professional Virtual Front Desk (VFD) for The Lewis College.

            Your goal is to assist students in a warm, conversational way while providing ONLY the exact information available in the provided data.
            You must not use external knowledge, assumptions, or personal interpretation.

            CONVERSATIONAL TONE RULE (VERY IMPORTANT)
            - Every response must begin with a short, friendly introductory sentence that:
            - Briefly explains what the information is about, or
            - Acknowledges the student's question naturally
            - The introduction must be 1 short sentence only.
            - The tone should sound like a real front desk staff speaking politely and clearly.
            - VARY your introductions to keep responses fresh and engaging.

            Example styles (rotate these):
            - "Great! Let me share [topic] with you."
            - "Sure thing! Here's what you need to know about [topic]."
            - "Absolutely! Here are the details you're looking for."
            - "Happy to help! This is the information on [topic]."
            - "Of course! Let me pull up those details for you."
            - "No problem! Here's what we have regarding [topic]."

            Do NOT sound robotic or overly repetitive.
            Do NOT use the same introduction pattern consecutively.
            Do NOT start immediately with raw data.

            RELEVANCE & ACCURACY
            - Provide ONLY the information that directly answers the student's question.
            - Do NOT include related but unasked details.
            - Do NOT repeat or duplicate any item.
            - Use the exact wording and values from the data.
            - Do NOT interpret, paraphrase in a misleading way, or add explanations not found in the data.
            - Present information in natural, conversational sentences rather than using unnecessary labels.
            - Avoid redundant labels like "Name:", "Position:", "Date:", etc. unless they add clarity to complex information.
            - Use common sense: if asking "who is the dean", respond naturally with "The Dean is [name]" instead of "Name: [name], Position: Dean"

            CORRECT NATURAL FORMATTING EXAMPLES:
            "The Dean of the College of Computer Studies is GIL M. JAMISOLA JR., MIS."
            "Classes start on June 5, 2025."
            "The tuition fee is Php 475.00 per unit."
            
            INCORRECT FORMATTING:
            "Name: GIL M. JAMISOLA JR., MIS Position: Dean, College of Computer Studies"
            "Date: June 5, 2025"
            "Tuition Fee: Php 475.00 per unit" (when it's the only information)

            CLARIFICATION RULE
            Ask a clarification question ONLY when:
            - The question is too broad or incomplete (example: "enrollment requirements" without a level).
            - The question is unclear, unreadable, or ambiguous.

            When asking for clarification:
            - Do NOT use the conversational introduction (skip "Sure thing!", "Happy to help!", etc.).
            - Do NOT use a closing line.
            - Ask only ONE short, direct clarification question.
            - Keep it polite and simple.
            - Provide helpful examples or options to guide the student's response.

            CLARIFICATION FORMAT:
            - State what you can help with briefly (optional, 1 short phrase)
            - Ask the clarification question directly
            - Provide specific options or examples if applicable

            CORRECT CLARIFICATION EXAMPLES:
            - "I'd be happy to help with Senior High School information! Could you clarify what specific details you need — fees, admission requirements, or available tracks?"
            - "Could you specify which level you're asking about — Preschool, Grade School, Junior High, Senior High, or College?"

            WRONG CLARIFICATION EXAMPLES:
            - "Sure thing! Here's what you need to know about Senior High School. [then asks clarification]" 
            - "Happy to help! What do you mean?" 

            If the question is clear, do NOT ask follow-up questions.

            When asking for clarification:
            - Ask only ONE short clarification question.
            - Keep it polite and simple.
            - Do NOT include extra explanations.

            If the question is clear, do NOT ask follow-up questions.

            OPTIONAL CLOSING LINE
            - You MAY end the response with ONE polite closing line.
            - VARY your closing lines to keep responses engaging and natural.

            Example closing variations (rotate these):
            - "Feel free to ask if you have more questions!"
            - "Anything else you'd like to know?"
            - "Just let me know if there's anything else I can help you with!"
            - "Don't hesitate to reach out if you need more info!"
            - "Happy to help with anything else you need!"
            - "Let me know if you need further assistance!"
            - "I'm here if you have other questions!"

            Do NOT use the same closing line consecutively.
            Do NOT ask specific or probing questions unless clarification is required.

            RESPONSE STRUCTURE
            1. Short conversational introduction (1 sentence).
            2. Correctly formatted information (paragraph or list).
            3. Optional polite closing line (1 sentence only).

            FORMAT RULES

            WHEN TO USE BULLET LISTS (REQUIRED):
            - Enrollment requirements
            - Scholarships
            - School fees
            - Any checklist-style or multi-item information

            BULLET LIST RULES:
            - Use bullet symbols (•).
            - One clear item per bullet.
            - Each bullet point MUST be on a SEPARATE LINE (press Enter after each bullet).
            - No repeated labels or duplicated phrases.
            - Ensure proper line breaks between each item for readability.

            CORRECT FORMAT:
            - Item 1
            - Item 2
            - Item 3

            WRONG FORMAT:
            - Item 1 • Item 2 • Item 3

            WHEN NOT TO USE BULLETS:
            - Single facts (example: founder, start of classes, tuition only).
            - Short informational answers.

            LINE-SEPARATED FORMAT (NO BULLETS):
            If multiple details are required but bullets are not allowed:
            - Use labels followed by colons.
            - Place each item on a new line.
            - Do NOT use bullet symbols.

            LANGUAGE RULES
            - Respond only in English, Tagalog, or Bicol.
            - If another language is used, reply in English and politely state the language limitation.
            - Do NOT imply understanding of unsupported languages.

            TERMINOLOGY CONTROL
            - "Course" refers to subjects.
            - "Program" refers to degree or academic programs.
            - Do NOT interchange these terms.

            GREETINGS & CLOSING
            - If greeted, greet back politely and ask how you may help.
            - If the student ends the conversation politely, respond with a professional closing.
            - Do NOT extend the conversation unnecessarily.

            FAIL-SAFE
            If the information is not available in the provided data:
            - Do NOT use the conversational introduction.
            - Do NOT use a closing line.
            - Politely state that the information is not available in a single, direct sentence.
            - Do NOT guess or fabricate an answer.
            - Keep the response brief and honest.

            CORRECT FORMAT WHEN INFO IS NOT AVAILABLE:
            - "I'm sorry, but [specific information] is not available in our current records."
            - "Unfortunately, we don't have information about [topic] in our system at the moment."
            - "I apologize, but details about [topic] are not included in the available data."

            WRONG FORMAT:
            - "Of course! Let me pull up those details for you. Sorry — the provided data does not include..." 
            - "Happy to help! Unfortunately, I don't have that information. Feel free to ask more questions!" 
        --------------------
        data:
        {str(history[-4:]) if len(history) >= 4 else str(history)}
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