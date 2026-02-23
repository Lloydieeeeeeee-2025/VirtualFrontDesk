import io
import base64
from typing import List, Tuple, Dict
from datetime import datetime
from dotenv import load_dotenv
from dbconnector.db import tlcchatmate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ChromaDBService import ChromaDBService
from pypdf import PdfReader
from EventDetection import EventDetection
from WebScraper import WebScraper
from VersionDetector import VersionDetector


class KnowledgeRepository(ChromaDBService):
    """Handles synchronization between database and ChromaDB with incremental indexing."""

    def __init__(self):
        load_dotenv()
        super().__init__()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
        self.event_detector = EventDetection(self)
        self.web_scraper = WebScraper()
        self.version_detector = VersionDetector()
        self.progress = {"step": None, "status": "idle"}

    def set_progress(self, step: str, status: str = "running"):
        """Update the current progress."""
        self.progress["step"] = step
        self.progress["status"] = status

    def get_progress(self):
        """Get the current progress."""
        return self.progress

    def _cleanup_all_collections(self):
        """Delete all orphaned collections and keep only the current one."""
        try:
            for collection in self.client.list_collections():
                if collection.name != self.collection_name:
                    try:
                        self.client.delete_collection(name=collection.name)
                    except Exception:
                        pass
        except Exception:
            pass

    def get_db_connection(self):
        """Get database connection."""
        try:
            return tlcchatmate()
        except Exception as e:
            print(f"Database connection failed: {e}")
            return None

    def decode_pdf_bytes(self, pdf_data) -> bytes:
        """Decode PDF data from various formats."""
        if pdf_data is None:
            return None
        if isinstance(pdf_data, bytes):
            if pdf_data.startswith(b'%PDF-'):
                return pdf_data
            try:
                decoded = base64.b64decode(pdf_data)
                if decoded.startswith(b'%PDF-'):
                    return decoded
            except Exception:
                pass
            return pdf_data
        if isinstance(pdf_data, str):
            try:
                decoded = base64.b64decode(pdf_data)
                if decoded.startswith(b'%PDF-'):
                    return decoded
            except Exception:
                pass
        return None

    def get_last_sync_time(self, collection) -> str:
        """Get the last sync timestamp from ChromaDB metadata."""
        try:
            result = collection.get(ids=["_sync_metadata"])
            if result['ids']:
                return result['metadatas'][0].get('last_sync', '1970-01-01 00:00:00')
        except Exception:
            pass
        return '1970-01-01 00:00:00'

    def update_sync_time(self, collection, current_time: str):
        """Update the last sync timestamp in ChromaDB."""
        collection.upsert(
            documents=["sync_metadata"],
            metadatas=[{"last_sync": current_time}],
            ids=["_sync_metadata"]
        )

    def _extract_program_identifier(self, content: str, document_name: str) -> str:
        """Extract program identifier from document content and name."""
        name_lower = document_name.lower() if document_name else ""
        content_sample = content[:2000].lower() if content else ""

        program_patterns = {
            'bsit':         ['bachelor of science in information technology', 'information technology', 'bsit'],
            'bsba_om':      ['operations management', 'bsba om', 'bsba-om'],
            'bsba_fm':      ['financial management', 'bsba fm', 'bsba-fm'],
            'bsba_mm':      ['marketing management', 'bsba mm', 'bsba-mm'],
            'bsentrep':     ['entrepreneurship', 'bsentrep', 'bs entrep'],
            'bsed_math':    ['bachelor of secondary education (math)', 'mathematics education'],
            'bsed_english': ['bachelor of secondary education (english)', 'english education'],
            'beed':         ['bachelor of elementary education', 'elementary education', 'beed'],
            'act_network':  ['act - networking', 'data communications and networking'],
            'act_data':     ['act - data engineering', 'data management'],
            'act_appdev':   ['act - applications development', 'applications development'],
            'tcp':          ['teacher certificate program', 'tcp'],
        }

        for program_key, patterns in program_patterns.items():
            for pattern in patterns:
                if pattern in name_lower:
                    return program_key

        for program_key, patterns in program_patterns.items():
            for pattern in patterns:
                if pattern in content_sample:
                    return program_key

        return ""

    def _extract_pdf_content(self, pdf_data, doc_id: str) -> str:
        """Extract text content from PDF binary data. Returns empty string on failure."""
        pdf_bytes = self.decode_pdf_bytes(pdf_data)
        if not pdf_bytes:
            return ""
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            content = "".join(page.extract_text() or "" for page in reader.pages)
            return content.strip()
        except Exception as e:
            print(f"Error reading PDF for {doc_id}: {e}")
            return ""

    def _process_handbook_data(self, conn, documents_data: List[dict]):
        """
        Fetch ALL handbooks including already-archived rows.
        The already_archived flag lets _build_archive_status exclude them from
        VersionDetector so the detector only ranks un-archived siblings and
        cannot accidentally mark the newest document for archiving.
        """
        try:
            conn.execute(
                "SELECT handbook_id, handbook_document, handbook_name, updated_at, archive_at "
                "FROM handbook"
            )
            for handbook_id, pdf_data, handbook_name, updated_at, archive_at in conn.fetchall():
                content = self._extract_pdf_content(pdf_data, f"handbook_{handbook_id}")
                if not content:
                    continue
                documents_data.append({
                    'id':               f'handbook_{handbook_id}',
                    'name':             handbook_name,
                    'content':          content,
                    'type':             'handbook',
                    'updated_at':       updated_at,
                    'already_archived': archive_at is not None,
                })
        except Exception as e:
            print(f"Error fetching handbook data: {e}")

    def _process_course_data(self, conn, documents_data: List[dict]):
        """
        Fetch ALL courses including already-archived rows.
        The already_archived flag lets _build_archive_status exclude them from
        VersionDetector so the detector only ranks un-archived siblings and
        cannot accidentally mark the newest document for archiving.
        """
        try:
            conn.execute(
                "SELECT course_id, course_document, document_name, updated_at, archive_at "
                "FROM course"
            )
            for course_id, pdf_data, document_name, updated_at, archive_at in conn.fetchall():
                content = self._extract_pdf_content(pdf_data, f"course_{course_id}")
                if not content:
                    continue
                documents_data.append({
                    'id':               f'course_{course_id}',
                    'name':             document_name,
                    'content':          content,
                    'type':             'course',
                    'updated_at':       updated_at,
                    'already_archived': archive_at is not None,
                })
        except Exception as e:
            print(f"Error fetching course data: {e}")

    def _process_faq_data(self, conn, documents_data: List[dict]):
        """Extract and store FAQ documents."""
        try:
            conn.execute("SELECT faq_id, question, updated_at FROM faqs")
            for faq_id, question, updated_at in conn.fetchall():
                if not question:
                    continue
                documents_data.append({
                    'id':               f'faq_{faq_id}',
                    'name':             f'FAQ {faq_id}',
                    'content':          question,
                    'type':             'faq',
                    'updated_at':       updated_at,
                    'already_archived': False,
                })
        except Exception as e:
            print(f"Error fetching FAQ data: {e}")

    def _build_archive_status(self, documents_data: List[dict]) -> Dict:
        """
        Build the final archive_status dict used for both ChromaDB metadata
        and the DB update.

        Two-step approach that prevents archiving the newest document:
          Step 1 — Documents already archived in the DB (already_archived=True)
                   are pre-marked is_archived=True and EXCLUDED from
                   VersionDetector.  This is critical: if we passed them in,
                   the detector would group old and new together and its sort
                   could pick the newest document as the one to archive.
          Step 2 — VersionDetector receives only the un-archived siblings.
                   Within that set it correctly identifies and archives the
                   older version (lower revision year / older updated_at).
        """
        already_archived_ids = {d['id'] for d in documents_data if d.get('already_archived')}
        unarchived_docs      = [d for d in documents_data if not d.get('already_archived')]

        # Let VersionDetector rank only the un-archived candidates.
        archive_status = self.version_detector.determine_archive_status(unarchived_docs)

        # Inject the already-archived set so every doc has an entry.
        for doc_id in already_archived_ids:
            if doc_id not in archive_status:
                archive_status[doc_id] = {'is_archived': True, 'archive_at': None}

        return archive_status

    def _chunk_and_store_documents(self, documents_data: List[dict], archive_status: Dict,
                                   documents: List[str], metadata: List[dict], ids: List[str]):
        """Chunk documents and prepare for ChromaDB storage."""
        for doc_data in documents_data:
            doc_id   = doc_data['id']
            content  = doc_data['content']
            doc_type = doc_data['type']
            doc_name = doc_data['name']

            archive_info = archive_status.get(doc_id)
            if archive_info is not None:
                is_archived = archive_info.get('is_archived', False)
            else:
                is_archived = doc_data.get('already_archived', False)

            chunks        = self.text_splitter.split_text(content)
            revision_info = self.version_detector.extract_all_revision_info(content)
            program_id    = (
                self._extract_program_identifier(content, doc_name)
                if doc_type == 'course' else ""
            )

            for idx, chunk in enumerate(chunks):
                documents.append(chunk)
                ids.append(f"{doc_id}_chunk_{idx}")
                metadata.append({
                    "source_id":        doc_id,
                    "data_type":        doc_type,
                    "document_name":    doc_name,
                    "chunk_index":      idx,
                    "is_archived":      is_archived,
                    "document_version": "archived" if is_archived else "current",
                    # ChromaDB metadata does not accept None — use 0 / "" as sentinels.
                    "revision_year":    revision_info.get('year') or 0,
                    "program_id":       program_id or "",
                })

    def _update_archive_status_in_db(self, db, archive_status: Dict, documents_data: List[dict]):
        """
        Write archive_at = NOW() only for documents that:
          - are newly determined to be archived (is_archived=True), AND
          - were NOT already archived in the DB (already_archived=False).
        This prevents overwriting an existing archive_at timestamp and ensures
        we never stamp the newest document by accident.
        """
        already_archived_ids = {d['id'] for d in documents_data if d.get('already_archived')}

        try:
            conn = db.cursor()
            updated_count = 0

            for doc_id, archive_info in archive_status.items():
                if not archive_info.get('is_archived'):
                    continue
                if doc_id in already_archived_ids:
                    continue

                if doc_id.startswith('handbook_'):
                    handbook_id = doc_id.replace('handbook_', '', 1)
                    conn.execute(
                        "UPDATE handbook SET archive_at = NOW() WHERE handbook_id = %s",
                        (handbook_id,)
                    )
                    updated_count += 1

                elif doc_id.startswith('course_'):
                    course_id = doc_id.replace('course_', '', 1)
                    conn.execute(
                        "UPDATE course SET archive_at = NOW() WHERE course_id = %s",
                        (course_id,)
                    )
                    updated_count += 1

            if updated_count > 0:
                db.commit()

        except Exception as e:
            print(f"Error updating archive status: {e}")
            db.rollback()

    def collect_all_documents(self, conn) -> Tuple[List[str], List[dict], List[str], Dict, List[dict]]:
        """Collect all documents from database and websites with version detection."""
        documents, metadata, ids = [], [], []
        documents_data = []

        try:
            self.set_progress("Analyzing")
            self._process_handbook_data(conn, documents_data)
            self._process_course_data(conn, documents_data)
            self._process_faq_data(conn, documents_data)
        except Exception as e:
            print(f"Error collecting documents: {e}")
            raise

        archive_status = self._build_archive_status(documents_data)

        self.set_progress("Chunking")
        self._chunk_and_store_documents(documents_data, archive_status, documents, metadata, ids)

        try:
            self.set_progress("Scraping")
            scraped_data = self.web_scraper.scrape_all_websites(self)
            if scraped_data:
                self.web_scraper.process_scraped_content(
                    scraped_data, documents, metadata, ids, self.text_splitter
                )
        except Exception as e:
            print(f"Error processing website data: {e}")

        return documents, metadata, ids, archive_status, documents_data

    def sync_data_to_chromadb(self) -> bool:
        """Main function to sync database data to ChromaDB with full recreation."""
        db = self.get_db_connection()
        if not db:
            self.set_progress("Error", "error")
            return False

        try:
            conn = db.cursor()
            self.set_progress("Starting", "running")

            self._cleanup_all_collections()

            documents, metadata, ids, archive_status, documents_data = self.collect_all_documents(conn)

            if not documents:
                db.close()
                self.set_progress("Completed", "completed")
                return False

            self._update_archive_status_in_db(db, archive_status, documents_data)

            try:
                self.client.delete_collection(name=self.collection_name)
            except Exception:
                pass

            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            collection.upsert(documents=documents, metadatas=metadata, ids=ids)

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.update_sync_time(collection, current_time)

            # Seed the event detector so check_for_updates never reports false
            # deletions on the first call after a fresh sync.
            self.event_detector.last_processed_ids = self.event_detector.get_current_document_ids()

            db.close()
            self.set_progress("Completed", "completed")
            return True

        except Exception as e:
            print(f"Error during sync: {e}")
            if db:
                db.close()
            self.set_progress("Error", "error")
            return False

    def check_updates_available(self) -> bool:
        """Check if there are any updates available in the database."""
        db = self.get_db_connection()
        if not db:
            return False

        try:
            collection = self.get_collection()
            last_sync_time = self.get_last_sync_time(collection)

            # Seed last_processed_ids on the first call after a fresh process
            # start so the deletion check does not produce false positives.
            if not self.event_detector.last_processed_ids:
                self.event_detector.last_processed_ids = (
                    self.event_detector.get_current_document_ids()
                )

            return self.event_detector.check_for_updates(db, last_sync_time)
        except Exception as e:
            print(f"Error checking updates: {e}")
            return False
        finally:
            if db:
                db.close()

    def _extract_base_id(self, chunk_id: str) -> str:
        """Extract base document ID from chunk ID."""
        if chunk_id.startswith('_sync_'):
            return None
        return chunk_id.split('_chunk_')[0] if '_chunk_' in chunk_id else chunk_id