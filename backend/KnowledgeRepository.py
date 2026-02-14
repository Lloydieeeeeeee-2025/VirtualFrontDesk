import io
import time
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

        self.progress = {
            "step": None,
            "status": "idle"
        }

    def set_progress(self, step: str, status: str = "running"):
        """Update the current progress."""
        self.progress["step"] = step
        self.progress["status"] = status
        print(f"[Progress] {step} - {status}")

    def get_progress(self):
        """Get the current progress."""
        return self.progress

    def _cleanup_all_collections(self):
        """Delete ALL orphaned collections and keep only the current one."""
        try:
            all_collections = self.client.list_collections()
            
            for collection in all_collections:
                col_name = collection.name
                if col_name != self.collection_name:
                    try:
                        self.client.delete_collection(name=col_name)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def get_db_connection(self):
        """Get database connection."""
        try:
            return tlcchatmate()
        except Exception as e:
            print(f"Database connection failed: {e}")
            return None

    def decode_pdf_bytes(self, pdf_data):
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
            except:
                pass
            return pdf_data

        if isinstance(pdf_data, str):
            try:
                decoded = base64.b64decode(pdf_data)
                if decoded.startswith(b'%PDF-'):
                    return decoded
            except:
                pass

        return None

    def get_last_sync_time(self, collection) -> str:
        """Get the last sync timestamp from ChromaDB metadata."""
        try:
            result = collection.get(ids=["_sync_metadata"])
            if result['ids']:
                return result['metadatas'][0].get('last_sync', '1970-01-01 00:00:00')
        except:
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
            'bsit': ['bachelor of science in information technology', 'information technology', 'bsit'],
            'bsba_om': ['operations management', 'bsba om', 'bsba-om'],
            'bsba_fm': ['financial management', 'bsba fm', 'bsba-fm'],
            'bsba_mm': ['marketing management', 'bsba mm', 'bsba-mm'],
            'bsentrep': ['entrepreneurship', 'bsentrep', 'bs entrep'],
            'bsed_math': ['bachelor of secondary education (math)', 'mathematics education'],
            'bsed_english': ['bachelor of secondary education (english)', 'english education'],
            'beed': ['bachelor of elementary education', 'elementary education', 'beed'],
            'act_network': ['act - networking', 'data communications and networking'],
            'act_data': ['act - data engineering', 'data management'],
            'act_appdev': ['act - applications development', 'applications development'],
            'tcp': ['teacher certificate program', 'tcp'],
        }
        
        for program_key, patterns in program_patterns.items():
            for pattern in patterns:
                if pattern in name_lower:
                    return program_key
        
        for program_key, patterns in program_patterns.items():
            for pattern in patterns:
                if pattern in content_sample:
                    return program_key
        
        return None

    def _process_handbook_data(self, conn, documents_data: List[dict]):
        """Extract and store handbook documents."""
        try:
            conn.execute("SELECT handbook_id, handbook_document, handbook_name, updated_at FROM Handbook "
                        "WHERE archive_at IS NULL")
            handbooks = conn.fetchall()
            print(f"Found {len(handbooks)} non-archived handbooks to process")
            
            for handbook_id, pdf_data, handbook_name, updated_at in handbooks:
                pdf_bytes = self.decode_pdf_bytes(pdf_data)
                if not pdf_bytes:
                    continue
                
                try:
                    pdf_stream = io.BytesIO(pdf_bytes)
                    reader = PdfReader(pdf_stream)
                    content = ""
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            content += text
                    
                    if not content or len(content.strip()) == 0:
                        continue
                    
                    documents_data.append({
                        'id': f'handbook_{handbook_id}',
                        'name': handbook_name,
                        'content': content,
                        'type': 'handbook',
                        'updated_at': updated_at
                    })
                except Exception as e:
                    print(f"Error processing handbook {handbook_id}: {e}")
        except Exception as e:
            print(f"Error fetching handbook data: {e}")

    def _process_course_data(self, conn, documents_data: List[dict]):
        """Extract and store course documents."""
        try:
            conn.execute("SELECT course_id, course_document, document_name, updated_at FROM Course "
                        "WHERE archive_at IS NULL")
            courses = conn.fetchall()
            print(f"Found {len(courses)} non-archived courses to process")
            
            for course_id, pdf_data, document_name, updated_at in courses:
                pdf_bytes = self.decode_pdf_bytes(pdf_data)
                if not pdf_bytes:
                    continue
                
                try:
                    pdf_stream = io.BytesIO(pdf_bytes)
                    reader = PdfReader(pdf_stream)
                    content = ""
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            content += text
                    
                    if not content or len(content.strip()) == 0:
                        continue
                    
                    documents_data.append({
                        'id': f'course_{course_id}',
                        'name': document_name,
                        'content': content,
                        'type': 'course',
                        'updated_at': updated_at
                    })
                except Exception as e:
                    print(f"Error processing course {course_id}: {e}")
        except Exception as e:
            print(f"Error fetching course data: {e}")

    def _process_faq_data(self, conn, documents_data: List[dict]):
        """Extract and store FAQ documents."""
        try:
            conn.execute("SELECT faq_id, question, updated_at FROM faqs")
            faqs = conn.fetchall()
            
            for faq_id, question, updated_at in faqs:
                if not question:
                    continue
                
                documents_data.append({
                    'id': f'faq_{faq_id}',
                    'name': f'FAQ {faq_id}',
                    'content': question,
                    'type': 'faq',
                    'updated_at': updated_at
                })
        except Exception as e:
            print(f"Error fetching FAQ data: {e}")

    def _chunk_and_store_documents(self, documents_data: List[dict], archive_status: Dict,
                                    documents: List[str], metadata: List[dict], ids: List[str]):
        """Chunk documents and prepare for ChromaDB storage."""
        print(f"Chunking {len(documents_data)} documents...")
        
        for doc_data in documents_data:
            doc_id = doc_data['id']
            content = doc_data['content']
            doc_type = doc_data['type']
            doc_name = doc_data['name']
            archive_info = archive_status.get(doc_id, {'is_archived': False})
            is_archived = archive_info.get('is_archived', False)
            
            chunks = self.text_splitter.split_text(content)
            
            for idx, chunk in enumerate(chunks):
                documents.append(chunk)
                chunk_id = f"{doc_id}_chunk_{idx}"
                ids.append(chunk_id)
                
                revision_info = self.version_detector.extract_all_revision_info(content)
                program_id = self._extract_program_identifier(content, doc_name) if doc_type == 'course' else None
                
                metadata.append({
                    "source_id": doc_id,
                    "data_type": doc_type,
                    "document_name": doc_name,
                    "chunk_index": idx,
                    "is_archived": is_archived,
                    "document_version": "archived" if is_archived else "current",
                    "revision_year": revision_info.get('year'),
                    "program_id": program_id
                })
        
        print(f"Chunking complete. Total chunks: {len(ids)}")

    def _update_archive_status_in_db(self, db, archive_status: Dict):
        """Update archive status in database for archived documents."""
        try:
            conn = db.cursor()
            updated_count = 0
            
            for doc_id, archive_info in archive_status.items():
                if archive_info.get('is_archived'):
                    if doc_id.startswith('handbook_'):
                        handbook_id = doc_id.replace('handbook_', '')
                        conn.execute("UPDATE Handbook SET archive_at = NOW() WHERE handbook_id = %s",
                                    (handbook_id,))
                        updated_count += 1
                    
                    elif doc_id.startswith('course_'):
                        course_id = doc_id.replace('course_', '')
                        conn.execute("UPDATE Course SET archive_at = NOW() WHERE course_id = %s",
                                    (course_id,))
                        updated_count += 1
            
            if updated_count > 0:
                db.commit()
                print(f"{updated_count} documents archived in database")
                
        except Exception as e:
            print(f"Error updating archive status: {e}")
            db.rollback()

    def collect_all_documents(self, conn) -> Tuple[List[str], List[dict], List[str], Dict]:
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

        print("Analyzing document versions...")
        archive_status = self.version_detector.determine_archive_status(documents_data)

        self.set_progress("Chunking")
        self._chunk_and_store_documents(documents_data, archive_status, documents, metadata, ids)

        try:
            self.set_progress("Scraping")
            print("Collecting website data...")
            scraped_data = self.web_scraper.scrape_all_websites(self)
            if scraped_data:
                self.web_scraper.process_scraped_content(scraped_data, documents, metadata, ids, self.text_splitter)
        except Exception as e:
            print(f"Error processing website data: {e}")

        return documents, metadata, ids, archive_status

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
            
            documents, metadata, ids, archive_status = self.collect_all_documents(conn)

            if not documents:
                db.close()
                self.set_progress("Completed", "completed")
                return False

            self._update_archive_status_in_db(db, archive_status)

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
            
            db.close()
            self.set_progress("Completed", "completed")
            return True

        except Exception as e:
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
        if chunk_id.startswith('handbook_'):
            return chunk_id.split('_chunk_')[0]
        elif chunk_id.startswith('course_'):
            return chunk_id.split('_chunk_')[0]
        elif chunk_id.startswith('url_'):
            return chunk_id.split('_chunk_')[0]
        elif chunk_id.startswith('faq_'):
            return chunk_id.split('_chunk_')[0]
        return chunk_id