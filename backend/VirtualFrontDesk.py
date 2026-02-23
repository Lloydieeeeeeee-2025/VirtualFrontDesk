import threading
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional
from SessionManager import SessionManager
from ChromaDBService import ChromaDBService
from KnowledgeRepository import KnowledgeRepository
from VersionDetector import VersionDetector
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

    # Minimum cosine similarity score for a retrieved chunk to be considered relevant.
    # ChromaDB uses cosine *distance* (0 = identical, 2 = opposite); we convert to
    # similarity as  1 - distance/2  so this threshold sits on the [0, 1] scale.
    RELEVANCE_THRESHOLD = 0.30

    # How many chunks to request from ChromaDB before score-filtering.
    RETRIEVAL_TOP_K = 15

    def __init__(self):
        load_dotenv()
        super().__init__()
        self.session_manager = SessionManager(max_history_per_session=4)
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.ph_timezone = pytz.timezone("Asia/Manila")
        self.version_detector = VersionDetector()

        self.intents = {
            "schedule": "asking about class schedule, timetable, or next class",
            "grades":   "asking about grades, marks, GPA, or academic performance",
            "soa":      "asking about statement of account, balance, assessment fees",
            "clearance":"asking about academic clearance",
            "general":  "asking about general questions such as enrollments, programs, courses, fees",
        }

        self.program_keywords = {
            "bsba_om":      ["operations management", "bsba om", "bsba-om"],
            "bsba_fm":      ["financial management", "bsba fm", "bsba-fm"],
            "bsba_mm":      ["marketing management", "bsba mm", "bsba-mm"],
            "bsentrep":     ["entrepreneurship", "bsentrep", "bs entrep"],
            "bsit":         ["bsit", "information technology", "it student"],
            "bsed_math":    ["bsed math", "bsed-math", "mathematics teacher"],
            "bsed_english": ["bsed english", "bsed-eng", "english teacher"],
            "beed":         ["beed", "elementary education", "elementary teacher"],
            "act_network":  ["networking", "act network", "act-network"],
            "act_data":     ["data engineering", "act data", "act-data"],
            "act_appdev":   ["applications development", "act app"],
            "tcp":          ["teacher certificate", "tcp"],
        }

        # Hard farewells — whole message must match one of these exactly.
        self.closing_keywords = {"bye", "goodbye", "see you", "good bye"}

        # Soft closings — only treated as closing when the *entire* message is
        # one of these phrases (after normalisation), with no additional words.
        self.soft_closing_phrases = {
            "okay thanks", "ok thanks", "thank you", "thanks",
            "okay", "ok", "done", "alright",
        }

    # -------------------------------------------------------------------------
    # Intent Detection
    # -------------------------------------------------------------------------

    def detect_intent(self, prompt: str) -> str:
        """Detect intent from user prompt using embeddings."""
        try:
            prompt_embedding = self.get_embedding(prompt)
            best_intent, best_score = "general", -1.0
            for intent_name, description in self.intents.items():
                score = self.calculate_cosine_similarity(
                    prompt_embedding, self.get_embedding(description)
                )
                if score > best_score:
                    best_score = score
                    best_intent = intent_name
            return best_intent
        except Exception:
            return "general"

    # -------------------------------------------------------------------------
    # Session & Conversation Helpers
    # -------------------------------------------------------------------------

    def _is_initial_conversation(self, history: List[dict]) -> bool:
        return len(history) == 0

    def _is_closing_message(self, prompt: str) -> bool:
        """
        Return True only when the message is unambiguously a farewell or
        standalone acknowledgement — not when those words appear mid-sentence.
        """
        normalised = prompt.lower().strip().rstrip("!")
        return normalised in self.closing_keywords or normalised in self.soft_closing_phrases

    def _extract_program_from_query(self, prompt: str) -> Optional[str]:
        prompt_lower = prompt.lower()
        for program_id, keywords in self.program_keywords.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    return program_id
        return None

    def _get_greeting(self) -> str:
        hour = datetime.now(self.ph_timezone).hour
        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 18:
            return "Good afternoon"
        return "Good evening"

    def build_conversational_query(self, history: List[dict], current_prompt: str) -> str:
        """
        Build a retrieval query enriched with the most recent *user* question.
        Previous assistant text is intentionally excluded to avoid diluting the
        embedding with verbose answer content that drifts away from the topic.
        """
        query_parts = [current_prompt]
        recent_user_messages = [
            m["content"] for m in history[-4:] if m["role"] == "user"
        ]
        if recent_user_messages:
            query_parts.append(f"Previous question: {recent_user_messages[-1]}")
        return " ".join(query_parts)

    def extract_main_topic(self, prompt: str, history: List[dict]) -> str:
        """Expand prompt with previous question context if this is a follow-up."""
        if len(history) < 2:
            return prompt
        last_user_messages = [m for m in history[-2:] if m["role"] == "user"]
        if not last_user_messages:
            return prompt
        if self.is_follow_up_question(prompt, last_user_messages[-1]["content"]):
            return f"{last_user_messages[-1]['content']} {prompt}"
        return prompt

    # -------------------------------------------------------------------------
    # Prompt Construction
    # -------------------------------------------------------------------------

    def _create_system_prompt(self, context: str, is_initial: bool,
                              has_archived_content: bool = False) -> str:
        """
        Build the system prompt.
        History is passed separately via the messages list — it must NOT be
        embedded here as well, to prevent double-injection that confuses the model.
        """
        greeting_line = ""
        if is_initial:
            greeting = self._get_greeting()
            greeting_line = (
                f"{greeting}! I'm TLC ChatMate, the virtual front desk of The Lewis College. "
                "I'm here to help with your questions about enrollment, programs, policies, and services.\n\n"
            )

        archived_note = ""
        if has_archived_content:
            archived_note = (
                "\nIMPORTANT NOTE: The DATABASE INFORMATION below contains content from an ARCHIVED "
                "(older / superseded) document because the student asked about a previous version. "
                "Clearly state that the information is from an older archived document and advise "
                "the student to verify current policies with the registrar or the relevant office.\n"
            )

        return f"""You are TLC ChatMate, the official virtual front desk of The Lewis College.

{greeting_line}YOUR ROLE:
Provide accurate, professional, and friendly academic or administrative assistance strictly from the verified college records provided below.

STRICT RESPONSE RULES — MUST FOLLOW:
1. Answer ONLY using the DATABASE INFORMATION section below.
2. If the exact information is not found in DATABASE INFORMATION, respond with:
   "I'm sorry, but I don't have information about [topic] in our current records. You may visit the registrar or contact our office for assistance."
   Do NOT attempt to answer from general knowledge when this situation occurs.
3. Do NOT guess, invent, assume, or use general knowledge outside of the provided DATABASE INFORMATION.
4. Do NOT say "Based on my knowledge", "I believe", "I think", or similar hedging phrases.
5. Do NOT fabricate details such as specific dates, amounts, requirements, or policies that are not explicitly stated in the database.
6. Keep answers concise — 1 to 3 sentences unless listing requirements, steps, or fees.
7. Use bullet points ONLY for: enrollment steps, fee breakdowns, checklists, or multi-item lists.
8. Respond in English, Filipino, or Bicol depending on the student's language. Default to English if uncertain.
9. If the student uses inappropriate or disruptive language, respond calmly:
   "Let's keep our conversation respectful and focused on your academic needs."
10. For greetings — respond warmly but briefly; do not repeat the greeting on follow-up messages.
11. For farewells — reply with a short, friendly closing message.
12. Never start your response with "I" as the first word.
{archived_note}
CONVERSATION FLOW:
- Greeting (only at the start or when appropriate)
- Direct, helpful answer from the database
- Clarifying or follow-up question if needed
- Friendly, professional closing tone

DATABASE INFORMATION (only authoritative source):
----------
{context}
----------
"""

    def _prepare_messages(
        self, system_prompt: str, history: List[dict], prompt: str
    ) -> List[dict]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": prompt})
        return messages

    # -------------------------------------------------------------------------
    # ChromaDB Retrieval
    # -------------------------------------------------------------------------

    def _query_collection(
        self, query: str, where_filter: dict, n_results: int = RETRIEVAL_TOP_K
    ) -> dict:
        """
        Query ChromaDB and return results including distance scores.
        Falls back to a broader filter (no program_id) if the filtered query
        returns no results.
        """
        empty = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        try:
            collection = self.get_collection()
            count = collection.count()
            if count == 0:
                return empty
            safe_n = min(n_results, count)
            return collection.query(
                query_texts=[query],
                n_results=safe_n,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            try:
                collection = self.get_collection()
                safe_n = min(n_results, collection.count())
                return collection.query(
                    query_texts=[query],
                    n_results=safe_n,
                    where={"is_archived": False},
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                return empty

    def _extract_context_from_results(self, results: dict) -> str:
        """
        Build a context string from retrieved chunks, filtering out chunks
        whose cosine similarity falls below RELEVANCE_THRESHOLD.

        ChromaDB returns cosine *distance* in [0, 2]; similarity = 1 - distance/2.
        Only chunks that clear the threshold are included so the model is never
        fed weakly-related content that could trigger hallucination.
        """
        docs      = results.get("documents", [[]])
        distances = results.get("distances", [[]])

        doc_list  = docs[0]      if docs      and isinstance(docs[0], list)      else docs
        dist_list = distances[0] if distances and isinstance(distances[0], list) else []

        context_parts = []
        for idx, doc in enumerate(doc_list):
            if not isinstance(doc, str) or not doc.strip():
                continue
            if idx < len(dist_list):
                similarity = 1.0 - dist_list[idx] / 2.0
                if similarity < self.RELEVANCE_THRESHOLD:
                    continue
            context_parts.append(doc.strip())

        return "\n\n".join(context_parts)

    def _retrieve_context(self, retrieval_query: str, prompt: str) -> tuple:
        """
        Retrieve context from ChromaDB with archive-awareness.

        Strategy
        --------
          - Normal questions       → only current chunks (is_archived=False).
          - "archived_only" query  → only archived chunks (is_archived=True).
            This fires when the student explicitly asks about the *old / previous*
            version with no mention of current content.
          - "include_archived" query (both old AND current mentioned, or a
            specific year is given) → archived chunks first (they are what the
            student asked about), then current chunks appended for reference.
          - has_archived_content=True is returned only when archived chunks are
            actually present so the system prompt can warn the student.

        Returns
        -------
        (context_string, has_archived_content)
        """
        archive_params = self.version_detector.should_include_archived(prompt)
        program_id     = self._extract_program_from_query(prompt)

        include_archived = archive_params.get("include_archived", False)
        archived_only    = archive_params.get("archived_only", False)
        specific_year    = archive_params.get("specific_year")

        # ------------------------------------------------------------------
        # Helper: build archived filter (with optional program scope)
        # ------------------------------------------------------------------
        def _archived_filter():
            if program_id:
                return {"$and": [{"is_archived": True}, {"program_id": program_id}]}
            return {"is_archived": True}

        # ------------------------------------------------------------------
        # Helper: fetch + optionally year-prioritise archived chunks
        # ------------------------------------------------------------------
        def _fetch_archived_context() -> str:
            results = self._query_collection(
                retrieval_query, _archived_filter(), n_results=self.RETRIEVAL_TOP_K
            )
            raw = self._extract_context_from_results(results)
            if raw and specific_year:
                raw = self._prioritise_year_chunks(results, specific_year)
            return raw

        # ------------------------------------------------------------------
        # Helper: fetch current chunks (with optional program scope)
        # ------------------------------------------------------------------
        def _fetch_current_context() -> str:
            if program_id:
                program_results = self._query_collection(
                    retrieval_query,
                    {"$and": [{"is_archived": False}, {"program_id": program_id}]},
                    n_results=self.RETRIEVAL_TOP_K,
                )
                general_results = self._query_collection(
                    retrieval_query,
                    {"is_archived": False},
                    n_results=self.RETRIEVAL_TOP_K,
                )
                return self._merge_contexts(program_results, general_results)
            results = self._query_collection(
                retrieval_query, {"is_archived": False}, n_results=self.RETRIEVAL_TOP_K
            )
            return self._extract_context_from_results(results)

        # ------------------------------------------------------------------
        # Branch on what the student is asking for
        # ------------------------------------------------------------------
        has_archived_content = False

        if not include_archived:
            # Normal question — return only the latest content.
            context = _fetch_current_context()

        elif archived_only:
            # Student asked explicitly about the old/previous version only
            # (no mention of current).  Return archived chunks exclusively so
            # the LLM answers from the older document, not the newest one.
            context = _fetch_archived_context()
            if context:
                has_archived_content = True
            else:
                # Graceful fallback: no archived chunks found → use current.
                context = _fetch_current_context()

        else:
            # Student asked about history AND current, or gave a specific year.
            # Archived chunks lead (they are the focus of the question);
            # current chunks are appended so the LLM can contrast if relevant.
            archived_context = _fetch_archived_context()
            current_context  = _fetch_current_context()
            if archived_context:
                context = self._merge_context_strings(archived_context, current_context)
                has_archived_content = True
            else:
                context = current_context

        return context, has_archived_content

    def _merge_context_strings(self, primary: str, secondary: str) -> str:
        """
        Merge two context strings, de-duplicating by chunk content.
        Primary chunks always appear first.
        """
        seen:   set       = set()
        merged: List[str] = []

        for chunk in primary.split("\n\n") + secondary.split("\n\n"):
            chunk = chunk.strip()
            if chunk and chunk not in seen:
                seen.add(chunk)
                merged.append(chunk)

        return "\n\n".join(merged)

    def _prioritise_year_chunks(self, results: dict, target_year: int) -> str:
        """
        Re-order retrieved archived chunks so those whose revision_year metadata
        matches target_year come first, then apply the normal relevance filter.
        """
        docs      = results.get("documents", [[]])
        distances = results.get("distances", [[]])
        metadatas = results.get("metadatas", [[]])

        doc_list  = docs[0]      if docs      and isinstance(docs[0], list)      else []
        dist_list = distances[0] if distances and isinstance(distances[0], list) else []
        meta_list = metadatas[0] if metadatas and isinstance(metadatas[0], list) else []

        prioritised: List[str] = []
        rest:        List[str] = []

        for idx, doc in enumerate(doc_list):
            if not isinstance(doc, str) or not doc.strip():
                continue
            if idx < len(dist_list):
                similarity = 1.0 - dist_list[idx] / 2.0
                if similarity < self.RELEVANCE_THRESHOLD:
                    continue
            meta = meta_list[idx] if idx < len(meta_list) else {}
            if meta.get("revision_year") == target_year:
                prioritised.append(doc.strip())
            else:
                rest.append(doc.strip())

        return "\n\n".join(prioritised + rest)

    def _merge_contexts(self, primary_results: dict, secondary_results: dict) -> str:
        """
        Merge two sets of retrieval results, de-duplicate by content, and
        apply relevance filtering to both.  Primary results take precedence.
        """
        return self._merge_context_strings(
            self._extract_context_from_results(primary_results),
            self._extract_context_from_results(secondary_results),
        )

    # -------------------------------------------------------------------------
    # History Management
    # -------------------------------------------------------------------------

    def _update_conversation_history(
        self, session_id: str, history: List[dict], prompt: str, ai_response: str
    ) -> None:
        history.append({"role": "user",      "content": prompt})
        history.append({"role": "assistant", "content": ai_response})
        self.session_manager.update_history(session_id, history[-8:])

    # -------------------------------------------------------------------------
    # Core Processing
    # -------------------------------------------------------------------------

    def process_prompt(self, request: PromptRequest) -> PromptResponse:
        """Process a student prompt and return a grounded, accurate response."""
        prompt               = request.prompt.strip()
        conversation_session = request.conversationSession

        intent = self.detect_intent(prompt)

        if not self.session_manager.session_exists(conversation_session):
            self.session_manager.create_session(conversation_session, request.username)

        history    = self.session_manager.get_session_history(conversation_session)
        is_initial = self._is_initial_conversation(history)

        # --- Closing message guard ---
        if self._is_closing_message(prompt):
            closing_response = (
                "Thank you for reaching out to TLC ChatMate! "
                "If you have more questions in the future, feel free to come back anytime. "
                "Have a great day!"
            )
            self._update_conversation_history(
                conversation_session, history, prompt, closing_response
            )
            return PromptResponse(
                success=True, response=closing_response, requires_auth=False, intent=intent
            )

        # --- Build retrieval query ---
        main_topic       = self.extract_main_topic(prompt, history)
        retrieval_query  = self.build_conversational_query(history, main_topic)

        # --- Retrieve context (archive-aware) ---
        context, has_archived_content = self._retrieve_context(retrieval_query, prompt)

        # --- Fallback when no relevant context is found ---
        if not context:
            ai_response = (
                "I'm sorry, but I don't have information about that topic in our current records. "
                "You may visit the registrar or contact our office directly for further assistance."
            )
            self._update_conversation_history(
                conversation_session, history, prompt, ai_response
            )
            return PromptResponse(
                success=True, response=ai_response, requires_auth=False, intent=intent
            )

        # --- Generate response ---
        system_prompt = self._create_system_prompt(context, is_initial, has_archived_content)
        messages      = self._prepare_messages(system_prompt, history, prompt)

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=500,
            top_p=0.9,
        )
        ai_response = response.choices[0].message.content.strip()

        self._update_conversation_history(conversation_session, history, prompt, ai_response)

        return PromptResponse(
            success=True, response=ai_response, requires_auth=False, intent=intent
        )

    def get_all_sessions(self) -> List[str]:
        return self.session_manager.get_all_sessions()


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app            = FastAPI()
vfd            = VirtualFrontDesk()
knowledge_repo = KnowledgeRepository()


@app.on_event("startup")
async def startup_event():
    def initial_sync():
        knowledge_repo.sync_data_to_chromadb()
    threading.Thread(target=initial_sync, daemon=True).start()


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
    metadata = vfd.session_manager.get_session_metadata(session_id)
    if not metadata:
        return {"error": "Session not found"}
    return metadata


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if vfd.session_manager.delete_session(session_id):
        return {"success": True, "message": f"Session {session_id} deleted"}
    return {"success": False, "message": "Session not found"}


@app.get("/admin/sync-status")
async def get_sync_status():
    return knowledge_repo.get_progress()


@app.post("/admin/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    if knowledge_repo.progress["status"] == "running":
        return {"success": False, "message": "Sync already in progress"}
    background_tasks.add_task(knowledge_repo.sync_data_to_chromadb)
    return {"success": True, "message": "Sync started"}


@app.get("/admin/check-updates")
async def check_updates():
    has_updates = knowledge_repo.check_updates_available()
    return {"updates_available": has_updates}


def start_fastapi_server():
    uvicorn.run("VirtualFrontDesk:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    start_fastapi_server()