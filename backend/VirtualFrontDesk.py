import threading
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Tuple
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

    RELEVANCE_THRESHOLD = 0.30
    RETRIEVAL_TOP_K = 15

    def __init__(self, knowledge_repo: KnowledgeRepository):
        load_dotenv()
        super().__init__()
        self.knowledge_repo = knowledge_repo
        self.session_manager = SessionManager(max_history_per_session=4)
        self.ph_timezone = pytz.timezone("Asia/Manila")
        self.version_detector = VersionDetector()

        self.intents = {
            "schedule": "asking about class schedule, timetable, or next class",
            "grades":   "asking about grades, marks, GPA, or academic performance",
            "soa":      "asking about statement of account, balance, assessment fees",
            "clearance": "asking about academic clearance",
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

        self.closing_keywords = {"bye", "goodbye", "see you", "good bye"}
        self.soft_closing_phrases = {
            "okay thanks", "ok thanks", "thank you", "thanks",
            "okay", "ok", "done", "alright",
        }

        self.confirmation_phrases = {
            "is that correct", "is that right", "are you sure", "are you certain",
            "is that accurate", "is that true", "are you confident", "is that confirmed",
            "really", "are you sure about that", "is that so", "can you confirm",
            "you sure", "is this correct", "is this right", "correct?", "right?",
        }

        self._empty_result = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    # -------------------------------------------------------------------------
    # Sync Readiness
    # -------------------------------------------------------------------------

    def _is_sync_ready(self) -> bool:
        """
        Return True only when the background sync has completed and the
        collection contains at least one non-metadata document.
        """
        if self.knowledge_repo.progress.get("status") != "completed":
            return False
        try:
            collection = self.get_collection()
            count = collection.count()
            return count > 1
        except Exception:
            return False

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
        normalised = prompt.lower().strip().rstrip("!")
        return normalised in self.closing_keywords or normalised in self.soft_closing_phrases

    def _is_confirmation_query(self, prompt: str, history: List[dict]) -> bool:
        """
        Return True when the student is asking to validate or confirm a
        previous answer rather than introducing a new topic.
        Requires at least one prior assistant message in history.
        """
        if not history:
            return False
        has_prior_answer = any(m["role"] == "assistant" for m in history)
        if not has_prior_answer:
            return False
        normalised = prompt.lower().strip().rstrip("?!.")
        return normalised in self.confirmation_phrases

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
        Build a retrieval query enriched with recent user context.
        For the very first question (no history) the prompt is used as-is so
        the embedding is focused and not diluted by empty context.
        Assistant messages are excluded to avoid diluting the embedding.
        """
        recent_user_messages = [
            m["content"] for m in history[-4:] if m["role"] == "user"
        ]
        if not recent_user_messages:
            return current_prompt
        return f"{current_prompt} Previous question: {recent_user_messages[-1]}"

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
        Build the system prompt. History is passed separately via the messages
        list and must NOT be embedded here to prevent double-injection.
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

    def _prepare_messages(self, system_prompt: str, history: List[dict], prompt: str) -> List[dict]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": prompt})
        return messages

    # -------------------------------------------------------------------------
    # ChromaDB Retrieval
    # -------------------------------------------------------------------------

    def _query_collection(self, query: str, where_filter: dict,
                          n_results: int = RETRIEVAL_TOP_K) -> dict:
        """
        Query ChromaDB and return results with distance scores.

        When the sync is confirmed complete but a filtered query still returns
        nothing, the method retries once with a force-refreshed client (in case
        the in-process handle is stale) then falls back to the broadest filter.
        """
        def _run_query(collection, where: dict) -> dict:
            count = collection.count()
            if count == 0:
                return self._empty_result
            safe_n = min(n_results, count)
            return collection.query(
                query_texts=[query],
                n_results=safe_n,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

        def _has_results(result: dict) -> bool:
            docs = result.get("documents", [[]])
            return bool(docs and docs[0])

        try:
            collection = self.get_collection()
            result = _run_query(collection, where_filter)

            if not _has_results(result):
                collection = self.get_collection(force_refresh=True)
                result = _run_query(collection, where_filter)

            broad_filter = {"is_archived": False}
            if not _has_results(result) and where_filter != broad_filter:
                result = _run_query(collection, broad_filter)

            return result

        except Exception:
            try:
                collection = self.get_collection(force_refresh=True)
                safe_n = min(n_results, collection.count())
                return collection.query(
                    query_texts=[query],
                    n_results=safe_n,
                    where={"is_archived": False},
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                return self._empty_result

    def _extract_context_from_results(self, results: dict) -> str:
        """
        Build a context string from retrieved chunks, filtering out chunks
        whose cosine similarity falls below RELEVANCE_THRESHOLD.
        ChromaDB returns cosine distance in [0, 2]; similarity = 1 - distance/2.
        """
        docs = results.get("documents", [[]])
        distances = results.get("distances", [[]])

        doc_list = docs[0] if docs and isinstance(docs[0], list) else []
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

    def _retrieve_context(self, retrieval_query: str, prompt: str) -> Tuple[str, bool]:
        """
        Retrieve context from ChromaDB with archive-awareness.

        Strategy:
          - Normal questions      → only current chunks (is_archived=False).
          - archived_only query   → only archived chunks; falls back to current.
          - include_archived query→ archived first, then current appended.
          - has_archived_content  → True only when archived chunks are present.
        """
        archive_params = self.version_detector.should_include_archived(prompt)
        program_id = self._extract_program_from_query(prompt)

        include_archived = archive_params.get("include_archived", False)
        archived_only = archive_params.get("archived_only", False)
        specific_year = archive_params.get("specific_year")

        def _archived_filter() -> dict:
            if program_id:
                return {"$and": [{"is_archived": True}, {"program_id": program_id}]}
            return {"is_archived": True}

        def _fetch_archived_context() -> str:
            results = self._query_collection(
                retrieval_query, _archived_filter(), n_results=self.RETRIEVAL_TOP_K
            )
            raw = self._extract_context_from_results(results)
            if raw and specific_year:
                raw = self._prioritise_year_chunks(results, specific_year)
            return raw

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

        has_archived_content = False

        if not include_archived:
            context = _fetch_current_context()

        elif archived_only:
            context = _fetch_archived_context()
            if context:
                has_archived_content = True
            else:
                context = _fetch_current_context()

        else:
            archived_context = _fetch_archived_context()
            current_context = _fetch_current_context()
            if archived_context:
                context = self._merge_context_strings(archived_context, current_context)
                has_archived_content = True
            else:
                context = current_context

        return context, has_archived_content

    def _merge_context_strings(self, primary: str, secondary: str) -> str:
        """Merge two context strings, de-duplicating by chunk content."""
        seen: set = set()
        merged: List[str] = []

        for chunk in primary.split("\n\n") + secondary.split("\n\n"):
            chunk = chunk.strip()
            if chunk and chunk not in seen:
                seen.add(chunk)
                merged.append(chunk)

        return "\n\n".join(merged)

    def _merge_contexts(self, primary_results: dict, secondary_results: dict) -> str:
        """Merge two retrieval result sets, de-duplicating and relevance-filtering both."""
        return self._merge_context_strings(
            self._extract_context_from_results(primary_results),
            self._extract_context_from_results(secondary_results),
        )

    def _prioritise_year_chunks(self, results: dict, target_year: int) -> str:
        """
        Re-order archived chunks so those whose revision_year metadata matches
        target_year appear first, then apply the normal relevance filter.
        """
        docs = results.get("documents", [[]])
        distances = results.get("distances", [[]])
        metadatas = results.get("metadatas", [[]])

        doc_list = docs[0] if docs and isinstance(docs[0], list) else []
        dist_list = distances[0] if distances and isinstance(distances[0], list) else []
        meta_list = metadatas[0] if metadatas and isinstance(metadatas[0], list) else []

        prioritised: List[str] = []
        rest: List[str] = []

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

    # -------------------------------------------------------------------------
    # History Management
    # -------------------------------------------------------------------------

    def _update_conversation_history(
        self, session_id: str, history: List[dict], prompt: str, ai_response: str
    ) -> None:
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": ai_response})
        self.session_manager.update_history(session_id, history[-8:])

    def _get_last_assistant_message(self, history: List[dict]) -> Optional[str]:
        """Return the most recent assistant message from history, or None."""
        for message in reversed(history):
            if message["role"] == "assistant":
                return message["content"]
        return None

    def _generate_closing_response(self, prompt: str, history: List[dict]) -> str:
        """
        Use GPT-4o-mini to generate a professional and friendly closing response
        that feels natural based on the conversation context.
        """
        system_prompt = (
            "You are TLC ChatMate, the official virtual front desk of The Lewis College. "
            "The student is wrapping up the conversation. "
            "Respond with a warm, sincere, and professional farewell that feels natural given the conversation. "
            "You may acknowledge what was discussed if appropriate, wish them well, and invite them to return anytime. "
            "Do NOT use hollow or repetitive phrases. "
            "Never start your response with 'I'. "
            "Keep it brief — 2 to 3 sentences at most."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            *history[-4:],
            {"role": "user", "content": prompt},
        ]
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.4,
            max_tokens=150,
            top_p=0.9,
        )
        return response.choices[0].message.content.strip()

    def _generate_confirmation_response(self, prompt: str, last_answer: str, history: List[dict]) -> str:
        """
        Use GPT-4o-mini to generate a professional and friendly confirmation
        response that re-affirms the previous answer without static phrasing.
        """
        system_prompt = (
            "You are TLC ChatMate, the official virtual front desk of The Lewis College. "
            "The student is asking you to confirm or validate your previous answer. "
            "Your job is to confidently re-affirm that your previous response was accurate, "
            "then briefly restate the key point(s) in a natural, friendly, and professional tone. "
            "Do NOT introduce any new information. "
            "Do NOT use generic filler phrases like 'Absolutely!' or 'Of course!' alone — always include the substance. "
            "Never start your response with 'I'. "
            "Keep the response concise — 2 to 3 sentences at most."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            *history[-4:],
            {"role": "user", "content": prompt},
        ]
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=200,
            top_p=0.9,
        )
        return response.choices[0].message.content.strip()

    # -------------------------------------------------------------------------
    # Core Processing
    # -------------------------------------------------------------------------

    def process_prompt(self, request: PromptRequest) -> PromptResponse:
        """Process a student prompt and return a grounded, accurate response."""
        prompt = request.prompt.strip()
        conversation_session = request.conversationSession

        intent = self.detect_intent(prompt)

        if not self.session_manager.session_exists(conversation_session):
            self.session_manager.create_session(conversation_session, request.username)

        history = self.session_manager.get_session_history(conversation_session)
        is_initial = self._is_initial_conversation(history)

        if self._is_closing_message(prompt):
            closing_response = self._generate_closing_response(prompt, history)
            self._update_conversation_history(
                conversation_session, history, prompt, closing_response
            )
            return PromptResponse(
                success=True, response=closing_response, requires_auth=False, intent=intent
            )

        # Guard: inform the student if the knowledge base is still loading.
        if not self._is_sync_ready():
            sync_response = (
                "TLC ChatMate is still loading the knowledge base. "
                "Please wait a moment and try again."
            )
            return PromptResponse(
                success=True, response=sync_response, requires_auth=False, intent=intent
            )

        # Handle confirmation queries by re-affirming the previous answer
        # instead of treating them as new retrieval requests.
        if self._is_confirmation_query(prompt, history):
            last_answer = self._get_last_assistant_message(history)
            if last_answer:
                confirmation_response = self._generate_confirmation_response(
                    prompt, last_answer, history
                )
                self._update_conversation_history(
                    conversation_session, history, prompt, confirmation_response
                )
                return PromptResponse(
                    success=True, response=confirmation_response, requires_auth=False, intent=intent
                )

        main_topic = self.extract_main_topic(prompt, history)
        retrieval_query = self.build_conversational_query(history, main_topic)

        context, has_archived_content = self._retrieve_context(retrieval_query, prompt)

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

        system_prompt = self._create_system_prompt(context, is_initial, has_archived_content)
        messages = self._prepare_messages(system_prompt, history, prompt)

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

app = FastAPI()
knowledge_repo = KnowledgeRepository()
vfd = VirtualFrontDesk(knowledge_repo)


@app.on_event("startup")
async def startup_event():
    threading.Thread(target=knowledge_repo.sync_data_to_chromadb, daemon=True).start()


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