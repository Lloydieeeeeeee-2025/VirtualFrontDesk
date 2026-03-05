import json
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
    TRANSLATED_RELEVANCE_THRESHOLD = 0.25
    RETRIEVAL_TOP_K = 15

    _TAGALOG_MARKERS = {
        "ako", "ikaw", "siya", "kami", "tayo", "kayo", "sila",
        "ko", "mo", "niya", "namin", "natin", "ninyo", "nila",
        "akin", "iyo", "kanya", "amin", "atin", "inyo", "kanila",
        "ang", "ng", "sa", "na", "at", "ay", "ni", "kay", "para",
        "kung", "pero", "kaya", "dahil", "kapag", "nang",
        "ano", "sino", "saan", "kailan", "bakit", "paano",
        "ito", "iyon", "dito", "doon", "nito", "noon",
        "mga", "rin", "din", "lang", "po", "ho",
        "hindi", "oo", "wala", "mayroon", "meron",
        "gusto", "puwede", "pwede", "kailangan",
        "magkano", "ilang", "gaano",
        "salamat", "kumusta", "magandang", "maayos",
        "tanong", "sagot", "tulong", "impormasyon",
        "enrolla", "enrolled", "pasok", "klase",
    }

    def __init__(self, knowledge_repo: KnowledgeRepository):
        load_dotenv()
        super().__init__()
        self.knowledge_repo = knowledge_repo
        self.session_manager = SessionManager(max_history_per_session=4)
        self.ph_timezone = pytz.timezone("Asia/Manila")
        self.version_detector = VersionDetector()
        self.llm_model = "gpt-4o-mini"

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

        self.closing_keywords = {
            "bye", "goodbye", "see you", "good bye",
            "paalam", "hanggang sa muli", "babay",
        }
        self.soft_closing_phrases = {
            "okay thanks", "ok thanks", "thank you", "thanks",
            "okay", "ok", "done", "alright",
            "salamat", "maraming salamat", "sige", "sige na",
            "ayos na", "tapos na", "okay na", "ok na", "ok lang",
        }
        self.confirmation_phrases = {
            "is that correct", "is that right", "are you sure", "are you certain",
            "is that accurate", "is that true", "are you confident", "is that confirmed",
            "really", "are you sure about that", "is that so", "can you confirm",
            "you sure", "is this correct", "is this right", "correct?", "right?",
            "tama ba", "tama ba iyon", "tama ba iyan", "sigurado ka ba",
            "sigurado ba", "totoo ba", "totoo ba iyon", "totoo ba iyan",
            "kumpirmado ba", "pwede mo bang kumpirmahin", "talaga ba",
            "talaga", "ganon ba", "ganoon ba", "tama ba yun", "tama ba yan",
        }

        self._empty_result = {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        self._no_info_response = {
            "english": (
                "I'm sorry, but I don't have information about that topic in our current records. "
                "You may visit the registrar or contact our office directly for further assistance."
            ),
            "tagalog": (
                "Paumanhin, wala akong impormasyon tungkol sa paksang iyon sa aming mga rekord. "
                "Maaari kang pumunta sa registrar o makipag-ugnayan sa aming opisina para sa karagdagang tulong."
            ),
        }

    # -------------------------------------------------------------------------
    # Language Detection
    # -------------------------------------------------------------------------

    def _detect_language(self, prompt: str) -> str:
        """Detect whether prompt is primarily English, Tagalog, or mixed."""
        tokens = set(prompt.lower().split())
        tagalog_hits = tokens & self._TAGALOG_MARKERS
        tagalog_ratio = len(tagalog_hits) / max(len(tokens), 1)
        if tagalog_ratio >= 0.4:
            return "tagalog"
        if tagalog_ratio >= 0.15:
            return "mixed"
        return "english"

    def _build_lang_instruction(self, lang: str) -> str:
        """Return a concise language instruction string for inline use."""
        if lang == "tagalog":
            return "The student is writing in Tagalog. Respond in Tagalog."
        if lang == "mixed":
            return "The student is mixing English and Tagalog. Mirror their language naturally."
        return "Respond in English."

    def _language_instruction(self, prompt: str) -> str:
        """
        Return the language-mirroring instruction to embed in the system prompt.
        Applies identical retrieval-grounded logic regardless of language.
        """
        lang = self._detect_language(prompt)
        if lang == "tagalog":
            return (
                "LANGUAGE: The student is writing in Tagalog. "
                "Respond entirely in Tagalog. "
                "Apply every response rule identically — use only the DATABASE INFORMATION "
                "provided, do not guess or add information not found in the database, "
                "and keep the same accuracy and professionalism as you would in English."
            )
        if lang == "mixed":
            return (
                "LANGUAGE: The student is mixing English and Tagalog. "
                "Mirror the student's language mix naturally (Taglish). "
                "Apply every response rule identically — use only the DATABASE INFORMATION "
                "provided, do not guess or add information not found in the database."
            )
        return "LANGUAGE: The student is writing in English. Respond in English."

    def _translate_to_english(self, prompt: str) -> str:
        """
        Translate a Tagalog or mixed-language prompt into English for ChromaDB
        retrieval only. Returns the original prompt unchanged for English input.
        """
        if self._detect_language(prompt) == "english":
            return prompt
        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a translator. Translate the following student question "
                            "into clear, natural English. Output ONLY the translated text — "
                            "no explanations, no quotation marks, no extra punctuation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=200,
            )
            translated = response.choices[0].message.content.strip()
            return translated if translated else prompt
        except Exception:
            return prompt

    def _get_no_info_response(self, lang: str) -> str:
        """Return the appropriate no-information response for the detected language."""
        return self._no_info_response.get(lang, self._no_info_response["english"])

    # -------------------------------------------------------------------------
    # Sync Readiness
    # -------------------------------------------------------------------------

    def _is_sync_ready(self) -> bool:
        """Return True only when sync has completed and the collection has data."""
        if self.knowledge_repo.progress.get("status") != "completed":
            return False
        try:
            return self.get_collection().count() > 1
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
        """Return True when the student is asking to validate a previous answer."""
        if not history:
            return False
        if not any(m["role"] == "assistant" for m in history):
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
        if 12 <= hour < 18:
            return "Good afternoon"
        return "Good evening"

    # -------------------------------------------------------------------------
    # Query Rewriting
    # -------------------------------------------------------------------------

    def rewrite_query_for_retrieval(
        self, prompt: str, history: List[dict], archive_params: Optional[dict] = None
    ) -> str:
        """
        Use an LLM to rewrite the student's prompt into a self-contained,
        semantically rich retrieval query in English.

        When archive_params indicates the student is asking about an older or
        archived version of a document, an explicit instruction is injected so
        the rewriter preserves — and enriches — the historical/archival intent.
        This ensures the ChromaDB semantic query matches archived chunk content
        even after pronoun resolution and entity expansion.
        """
        history_summary = self._summarise_history_for_rewriter(history)

        archive_instruction = ""
        if archive_params and archive_params.get("include_archived"):
            specific_year = archive_params.get("specific_year")
            if specific_year:
                archive_instruction = (
                    f"\n10. ARCHIVE QUERY — the student is asking about a SPECIFIC OLDER VERSION "
                    f"from {specific_year}. The rewritten query MUST include the year {specific_year} "
                    f"and terms like 'archived', 'old version', or 'previous version' so it matches "
                    f"archived document chunks in the vector database."
                )
            else:
                archive_instruction = (
                    "\n10. ARCHIVE QUERY — the student is asking about an OLDER or PREVIOUS version "
                    "of a document. The rewritten query MUST preserve historical intent by including "
                    "terms like 'archived', 'old version', 'previous version', or 'superseded' so it "
                    "matches archived document chunks in the vector database."
                )

        system_content = (
            "You are a search-query rewriter for a Philippine college knowledge-base chatbot. "
            "Your job is to convert a student's question into a single, self-contained English "
            "search query that will retrieve the most relevant document chunks from a vector database.\n\n"
            "RULES:\n"
            "1. Output ONLY the rewritten query — no explanation, no punctuation outside the query.\n"
            "2. Resolve all pronouns, ellipsis, and implicit references using the conversation history.\n"
            "3. Expand partial entity references to their likely full form "
            "(e.g. 'her name' → 'registrar full name', 'the dean' → 'dean name contact').\n"
            "4. Include relevant synonyms or alternate phrasings that may appear in college documents "
            "(e.g. 'how much' → 'tuition fee amount assessment', 'who is in charge' → 'head officer name position').\n"
            "5. PHILIPPINE ACADEMIC TERMINOLOGY — always apply these mappings before generating the query:\n"
            "   - 'subject' or 'subjects' → 'course' or 'courses' "
            "(in the Philippines, 'subject' means an academic course/unit, e.g. Math, English)\n"
            "   - 'course' or 'courses' → 'program' or 'programs' "
            "(in the Philippines, 'course' means a degree program, e.g. BSIT, BSBA)\n"
            "   Apply this mapping silently — do not explain it in the output.\n"
            "6. PROGRAM NAME — always include the full, specific program name when the student "
            "mentions or implies a program (e.g. 'ACT AppDev' → 'ACT Applications Development', "
            "'networking' → 'ACT Networking', 'data engineering' → 'ACT Data Engineering', "
            "'BSIT' → 'Bachelor of Science in Information Technology BSIT'). "
            "This is critical because multiple programs share identical subject names.\n"
            "7. If the question is already clear and complete, return it with minor enrichment only.\n"
            "8. Always write the output in English regardless of the student's input language.\n"
            "9. Keep the rewritten query concise — no more than 30 words."
            f"{archive_instruction}"
        )
        user_content = (
            f"CONVERSATION HISTORY (most recent):\n{history_summary}\n\n"
            f"STUDENT'S CURRENT QUESTION: {prompt}\n\n"
            "Rewritten retrieval query:"
        )

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                max_tokens=80,
            )
            rewritten = response.choices[0].message.content.strip()
            return rewritten if rewritten else prompt
        except Exception:
            return prompt

    def _summarise_history_for_rewriter(self, history: List[dict]) -> str:
        """
        Build a compact history string for the query rewriter.
        Includes the last 3 user messages and the last assistant message.
        """
        if not history:
            return "(no prior conversation)"

        recent = history[-6:]
        lines = []
        last_assistant = None

        for msg in recent:
            if msg["role"] == "user":
                lines.append(f"Student: {msg['content']}")
            elif msg["role"] == "assistant":
                last_assistant = msg["content"]

        if last_assistant:
            truncated = last_assistant[:300] + ("…" if len(last_assistant) > 300 else "")
            lines.append(f"Assistant: {truncated}")

        return "\n".join(lines) if lines else "(no prior conversation)"

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
                              prompt: str = "", has_archived_content: bool = False) -> str:
        """Build the system prompt. History is passed separately via messages list."""
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

        language_instruction = self._language_instruction(prompt)

        return f"""You are TLC ChatMate, the official virtual front desk of The Lewis College.

{greeting_line}YOUR ROLE:
Provide accurate, professional, and friendly academic or administrative assistance strictly from the verified college records provided below.

STRICT RESPONSE RULES — MUST FOLLOW:
1. Answer ONLY using the DATABASE INFORMATION section below.
2. If the exact information is not found in DATABASE INFORMATION, respond with:
   "I'm sorry, but I don't have information about [topic] in our current records. You may visit the registrar or contact our office for assistance."
   (Translate this message to match the student's language when applicable.)
   Do NOT attempt to answer from general knowledge when this situation occurs.
3. Do NOT guess, invent, assume, or use general knowledge outside of the provided DATABASE INFORMATION.
4. Do NOT say "Based on my knowledge", "I believe", "I think", or similar hedging phrases.
5. Do NOT fabricate details such as specific dates, amounts, requirements, or policies that are not explicitly stated in the database.
6. Keep answers concise — 1 to 3 sentences unless listing requirements, steps, or fees.
7. Use bullet points ONLY for: enrollment steps, fee breakdowns, checklists, or multi-item lists.
8. {language_instruction}
9. Supported languages are English and Tagalog ONLY. Do NOT respond in any other language.
10. If the student uses inappropriate or disruptive language, respond calmly:
    "Let's keep our conversation respectful and focused on your academic needs."
    (Translate to match the student's language when applicable.)
11. For greetings — respond warmly but briefly; do not repeat the greeting on follow-up messages.
12. For farewells — reply with a short, friendly closing message.
13. Never start your response with "I" as the first word.
14. PHILIPPINE ACADEMIC TERMINOLOGY — students at The Lewis College use local terminology:
    - When a student says "subject" or "subjects", they mean an academic COURSE or unit
      (e.g. Mathematics, English, PE). Match this against course/subject records.
    - When a student says "course" or "courses", they mean a degree PROGRAM
      (e.g. BSIT, BSBA, BEED). Match this against program records.
    - Always interpret the student's words using this mapping and respond using
      the same terminology the student used — do NOT correct or lecture them about it.
15. SUBJECT LIST VERIFICATION — when the student asks for subjects in a specific year and semester:
    a. First locate the exact YEAR label (e.g. "FIRST YEAR", "SECOND YEAR") AND the exact
       SEMESTER label (e.g. "FIRST SEMESTER", "SECOND SEMESTER") inside the DATABASE INFORMATION.
    b. List ONLY the subjects that appear under BOTH the matching year AND the matching semester.
       Do NOT list subjects from a different year or a different semester even if they are nearby.
    c. If the requested year or semester label does not exist anywhere in the DATABASE INFORMATION,
       respond: "I'm sorry, but [program name] does not have a [year] [semester] in its curriculum.
       Please check the year and semester and try again."
       (Translate to match the student's language when applicable.)
    d. Never infer or guess which year/semester a subject belongs to.
       Only list subjects that are explicitly listed under that year and semester label.
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

    # -------------------------------------------------------------------------
    # ChromaDB Retrieval
    # -------------------------------------------------------------------------

    def _query_collection(self, query: str, where_filter: dict,
                          n_results: int = RETRIEVAL_TOP_K) -> dict:
        """
        Query ChromaDB and return results with distance scores.
        Retries with a force-refreshed client when an initial query returns
        nothing, then falls back to the broadest non-archived filter.
        """
        broad_filter = {"is_archived": False}

        def _run_query(collection, where: dict) -> dict:
            count = collection.count()
            if count == 0:
                return self._empty_result
            return collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
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

            if not _has_results(result) and where_filter != broad_filter:
                result = _run_query(collection, broad_filter)

            return result

        except Exception:
            try:
                collection = self.get_collection(force_refresh=True)
                return collection.query(
                    query_texts=[query],
                    n_results=min(n_results, collection.count()),
                    where=broad_filter,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                return self._empty_result

    def _extract_context_from_results(self, results: dict,
                                       threshold: Optional[float] = None) -> str:
        """
        Build a context string from retrieved chunks, filtering out chunks
        below the relevance threshold.
        ChromaDB returns cosine distance in [0, 2]; similarity = 1 - distance/2.
        """
        effective_threshold = threshold if threshold is not None else self.RELEVANCE_THRESHOLD
        doc_list = (results.get("documents", [[]])[0] or [])
        dist_list = (results.get("distances", [[]])[0] or [])

        context_parts = []
        for idx, doc in enumerate(doc_list):
            if not isinstance(doc, str) or not doc.strip():
                continue
            if idx < len(dist_list):
                similarity = 1.0 - dist_list[idx] / 2.0
                if similarity < effective_threshold:
                    continue
            context_parts.append(doc.strip())

        return "\n\n".join(context_parts)

    def _rerank_chunks(self, query: str, chunks: List[str], top_n: int = 5) -> List[str]:
        """
        Use the LLM to rerank retrieved chunks by relevance to the query.
        Falls back to the original order when the LLM call fails or returns
        unparseable output.
        """
        if not chunks:
            return chunks

        numbered = "\n\n".join(f"[{i + 1}] {chunk}" for i, chunk in enumerate(chunks))
        system_content = (
            "You are a relevance ranker for a college knowledge-base chatbot. "
            "Given a student query and a list of numbered text chunks, "
            "output ONLY a JSON array of integers representing the chunk numbers "
            "in descending order of relevance to the query. "
            "Include only chunks that are actually relevant. "
            "Output format example: [3, 1, 5, 2]"
        )
        user_content = (
            f"STUDENT QUERY: {query}\n\n"
            f"CHUNKS:\n{numbered}\n\n"
            f"Return the top {top_n} most relevant chunk numbers as a JSON array."
        )

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                max_tokens=100,
            )
            raw = response.choices[0].message.content.strip().strip("` \n").lstrip("json").strip()
            ranked_indices = json.loads(raw)
            seen: set = set()
            reranked = []
            for idx in ranked_indices:
                i = int(idx) - 1
                if 0 <= i < len(chunks) and i not in seen:
                    seen.add(i)
                    reranked.append(chunks[i])
            return reranked if reranked else chunks[:top_n]
        except Exception:
            return chunks[:top_n]

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

    def _prioritise_year_chunks(self, results: dict, target_year: int,
                                threshold: Optional[float] = None) -> str:
        """
        Re-order archived chunks so those whose revision_year metadata matches
        target_year appear first, then apply the normal relevance filter.
        """
        effective_threshold = threshold if threshold is not None else self.RELEVANCE_THRESHOLD
        doc_list = (results.get("documents", [[]])[0] or [])
        dist_list = (results.get("distances", [[]])[0] or [])
        meta_list = (results.get("metadatas", [[]])[0] or [])

        prioritised: List[str] = []
        rest: List[str] = []

        for idx, doc in enumerate(doc_list):
            if not isinstance(doc, str) or not doc.strip():
                continue
            if idx < len(dist_list):
                similarity = 1.0 - dist_list[idx] / 2.0
                if similarity < effective_threshold:
                    continue
            meta = meta_list[idx] if idx < len(meta_list) else {}
            if meta.get("revision_year") == target_year:
                prioritised.append(doc.strip())
            else:
                rest.append(doc.strip())

        return "\n\n".join(prioritised + rest)

    def _retrieve_context(self, retrieval_query: str, prompt: str,
                          translated_query: str) -> Tuple[str, bool]:
        """
        Retrieve context from ChromaDB with archive-awareness.

        retrieval_query  – LLM-rewritten query built from history + topic.
        prompt           – original student prompt (archive params / language).
        translated_query – English translation of retrieval_query for Tagalog/mixed input.

        Program detection checks both the original prompt and the rewritten
        retrieval_query so that queries where the program name is only resolved
        during rewriting still get the correct filter.

        When a program_id is detected, only chunks tagged with that program_id
        are retrieved — no merging with the general pool.
        """
        archive_params = self.version_detector.should_include_archived(prompt)
        program_id = (
            self._extract_program_from_query(prompt)
            or self._extract_program_from_query(retrieval_query)
        )

        include_archived = archive_params.get("include_archived", False)
        archived_only = archive_params.get("archived_only", False)
        specific_year = archive_params.get("specific_year")

        is_translated = translated_query != retrieval_query
        threshold = (
            self.TRANSLATED_RELEVANCE_THRESHOLD if is_translated else self.RELEVANCE_THRESHOLD
        )
        query_for_chroma = translated_query

        def _archived_filter() -> dict:
            if program_id:
                return {"$and": [{"is_archived": True}, {"program_id": program_id}]}
            return {"is_archived": True}

        def _fetch_archived_context() -> str:
            results = self._query_collection(
                query_for_chroma, _archived_filter(), n_results=self.RETRIEVAL_TOP_K
            )
            raw = self._extract_context_from_results(results, threshold)
            if raw and specific_year:
                raw = self._prioritise_year_chunks(results, specific_year, threshold)
            return raw

        def _fetch_current_context() -> str:
            if program_id:
                results = self._query_collection(
                    query_for_chroma,
                    {"$and": [{"is_archived": False}, {"program_id": program_id}]},
                    n_results=self.RETRIEVAL_TOP_K,
                )
                return self._extract_context_from_results(results, threshold)

            results = self._query_collection(
                query_for_chroma, {"is_archived": False}, n_results=self.RETRIEVAL_TOP_K
            )
            return self._extract_context_from_results(results, threshold)

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

        if context:
            raw_chunks = [c for c in context.split("\n\n") if c.strip()]
            reranked_chunks = self._rerank_chunks(retrieval_query, raw_chunks, top_n=5)
            context = "\n\n".join(reranked_chunks)

        return context, has_archived_content

    # -------------------------------------------------------------------------
    # History Management
    # -------------------------------------------------------------------------

    def _update_conversation_history(
        self, session_id: str, history: List[dict], prompt: str, ai_response: str
    ) -> None:
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": ai_response})
        self.session_manager.update_history(session_id, history[-8:])

    # -------------------------------------------------------------------------
    # LLM Response Generators
    # -------------------------------------------------------------------------

    def _call_llm(self, system_prompt: str, history: List[dict],
                  prompt: str, temperature: float, max_tokens: int) -> str:
        """Shared helper to call the LLM and return the response text."""
        messages = [
            {"role": "system", "content": system_prompt},
            *history[-4:],
            {"role": "user", "content": prompt},
        ]
        response = self.openai_client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
        )
        return response.choices[0].message.content.strip()

    def _generate_closing_response(self, prompt: str, history: List[dict]) -> str:
        """Generate a warm, language-aware closing response."""
        lang = self._detect_language(prompt)
        lang_instruction = self._build_lang_instruction(lang)
        system_prompt = (
            "You are TLC ChatMate, the official virtual front desk of The Lewis College. "
            "The student is wrapping up the conversation. "
            "Respond with a warm, sincere, and professional farewell that feels natural given the conversation. "
            "You may acknowledge what was discussed if appropriate, wish them well, and invite them to return anytime. "
            "Do NOT use hollow or repetitive phrases. "
            "Never start your response with 'I'. "
            f"Keep it brief — 2 to 3 sentences at most. {lang_instruction}"
        )
        return self._call_llm(system_prompt, history, prompt, temperature=0.4, max_tokens=150)

    def _generate_confirmation_response(self, prompt: str, context: str,
                                        history: List[dict]) -> str:
        """
        Generate a language-aware confirmation response grounded in live database
        context. If the context is empty (the document was deleted since the last
        response), the VFD honestly admits it no longer has that information instead
        of blindly re-affirming stale history.
        """
        lang = self._detect_language(prompt)
        lang_instruction = self._build_lang_instruction(lang)

        if not context:
            if lang == "tagalog":
                return (
                    "Paumanhin, ang impormasyong iyon ay wala na sa aming mga kasalukuyang rekord. "
                    "Maaari kang pumunta sa registrar o makipag-ugnayan sa aming opisina para sa karagdagang tulong."
                )
            return (
                "Apologies, but that information is no longer available in our current records. "
                "You may visit the registrar or contact our office directly for further assistance."
            )

        system_prompt = (
            "You are TLC ChatMate, the official virtual front desk of The Lewis College. "
            "The student is asking you to confirm or validate your previous answer. "
            "Your job is to confidently re-affirm that your previous response was accurate "
            "using ONLY the DATABASE INFORMATION provided below. "
            "Do NOT introduce any new information. "
            "Do NOT use generic filler phrases like 'Absolutely!' or 'Of course!' alone — always include the substance. "
            "Never start your response with 'I'. "
            f"Keep the response concise — 2 to 3 sentences at most. {lang_instruction}\n\n"
            f"DATABASE INFORMATION:\n----------\n{context}\n----------"
        )
        return self._call_llm(system_prompt, history, prompt, temperature=0.3, max_tokens=200)

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

        if not self._is_sync_ready():
            lang = self._detect_language(prompt)
            sync_response = (
                "Nilo-load pa ng TLC ChatMate ang knowledge base. "
                "Mangyaring maghintay ng ilang sandali at subukan muli."
                if lang == "tagalog"
                else (
                    "TLC ChatMate is still loading the knowledge base. "
                    "Please wait a moment and try again."
                )
            )
            return PromptResponse(
                success=True, response=sync_response, requires_auth=False, intent=intent
            )

        # Resolve archive intent before rewriting so the rewriter can preserve it.
        archive_params = self.version_detector.should_include_archived(prompt)

        # LLM-rewritten retrieval query — resolves pronouns, ellipsis, entity
        # references, and preserves archival intent when required.
        retrieval_query = self.rewrite_query_for_retrieval(prompt, history, archive_params)
        translated_query = self._translate_to_english(retrieval_query)

        # Confirmation queries re-validate against the live database context so
        # that deleted documents no longer produce stale re-affirmations.
        if self._is_confirmation_query(prompt, history):
            context, _ = self._retrieve_context(retrieval_query, prompt, translated_query)
            confirmation_response = self._generate_confirmation_response(
                prompt, context, history
            )
            self._update_conversation_history(
                conversation_session, history, prompt, confirmation_response
            )
            return PromptResponse(
                success=True, response=confirmation_response, requires_auth=False, intent=intent
            )

        context, has_archived_content = self._retrieve_context(
            retrieval_query, prompt, translated_query
        )

        if not context:
            lang = self._detect_language(prompt)
            ai_response = self._get_no_info_response(lang)
            self._update_conversation_history(
                conversation_session, history, prompt, ai_response
            )
            return PromptResponse(
                success=True, response=ai_response, requires_auth=False, intent=intent
            )

        system_prompt = self._create_system_prompt(
            context, is_initial, prompt=prompt, has_archived_content=has_archived_content
        )
        messages = [
            {"role": "system", "content": system_prompt},
            *history[-4:],
            {"role": "user", "content": prompt},
        ]

        response = self.openai_client.chat.completions.create(
            model=self.llm_model,
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


def _run_sync():
    """Run a full sync and clear all session histories afterwards."""
    knowledge_repo.sync_data_to_chromadb()
    vfd.session_manager.clear_all_histories()


@app.on_event("startup")
async def startup_event():
    threading.Thread(target=_run_sync, daemon=True).start()


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
    background_tasks.add_task(_run_sync)
    return {"success": True, "message": "Sync started"}


@app.get("/admin/check-updates")
async def check_updates():
    has_updates = knowledge_repo.check_updates_available()
    return {"updates_available": has_updates}


def start_fastapi_server():
    uvicorn.run("VirtualFrontDesk:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    start_fastapi_server()