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
        self.sync_interval = 10
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False
        )
        self.event_detector = EventDetection(self)
        self.web_scraper = WebScraper()
        self.version_detector = VersionDetector()

    def _cleanup_all_collections(self):
        """Delete ALL orphaned collections and keep only the current one."""
        try:
            all_collections = self.client.list_collections()
            print(f"\n🔍 Found {len(all_collections)} total collections in ChromaDB")
            
            for collection in all_collections:
                col_name = collection.name
                if col_name != self.collection_name:
                    print(f"🗑️ Removing orphaned collection: {col_name}")
                    try:
                        self.client.delete_collection(name=col_name)
                        print(f"   ✓ Deleted: {col_name}")
                    except Exception as e:
                        print(f"   ✗ Failed to delete {col_name}: {e}")
            
            print(f"✓ Cleanup complete - only '{self.collection_name}' will remain")
        except Exception as e:
            print(f"✗ Error during cleanup: {e}")

    def get_db_connection(self):
        """Get database connection."""
        try:
            return tlcchatmate()
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
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
            print(f"📋 Found {len(handbooks)} non-archived handbooks to process")
            
            for handbook_id, pdf_data, handbook_name, updated_at in handbooks:
                pdf_bytes = self.decode_pdf_bytes(pdf_data)
                if not pdf_bytes:
                    print(f"⚠️ Could not decode handbook {handbook_id}")
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
                        print(f"⚠️ Handbook {handbook_id} has no extractable text content")
                        continue
                    
                    documents_data.append({
                        'id': f'handbook_{handbook_id}',
                        'name': handbook_name,
                        'content': content,
                        'type': 'handbook',
                        'updated_at': updated_at
                    })
                    print(f"✓ Handbook {handbook_id} loaded: {len(content)} chars")
                except Exception as e:
                    print(f"✗ Error processing handbook {handbook_id}: {e}")
        except Exception as e:
            print(f"✗ Error fetching handbook data: {e}")

    def _process_course_data(self, conn, documents_data: List[dict]):
        """Extract and store course documents."""
        try:
            conn.execute("SELECT course_id, course_document, document_name, updated_at FROM Course "
                        "WHERE archive_at IS NULL")
            courses = conn.fetchall()
            print(f"📋 Found {len(courses)} non-archived courses to process")
            
            for course_id, pdf_data, document_name, updated_at in courses:
                pdf_bytes = self.decode_pdf_bytes(pdf_data)
                if not pdf_bytes:
                    print(f"⚠️ Could not decode course {course_id}")
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
                        print(f"⚠️ Course {course_id} has no extractable text content")
                        continue
                    
                    documents_data.append({
                        'id': f'course_{course_id}',
                        'name': document_name,
                        'content': content,
                        'type': 'course',
                        'updated_at': updated_at
                    })
                    print(f"✓ Course {course_id} loaded: {len(content)} chars")
                except Exception as e:
                    print(f"✗ Error processing course {course_id}: {e}")
        except Exception as e:
            print(f"✗ Error fetching course data: {e}")

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
                print(f"✓ FAQ {faq_id} loaded: {len(question)} chars")
        except Exception as e:
            print(f"✗ Error fetching FAQ data: {e}")

    def _chunk_and_store_documents(self, documents_data: List[dict], archive_status: Dict,
                                    documents: List[str], metadata: List[dict], ids: List[str]):
        """Chunk documents and prepare for ChromaDB storage."""
        print(f"\n📊 Chunking {len(documents_data)} documents...")
        
        for doc_data in documents_data:
            doc_id = doc_data['id']
            content = doc_data['content']
            doc_type = doc_data['type']
            doc_name = doc_data['name']
            archive_info = archive_status.get(doc_id, {'is_archived': False})
            is_archived = archive_info.get('is_archived', False)
            
            chunks = self.text_splitter.split_text(content)
            status = "ARCHIVED" if is_archived else "CURRENT"
            print(f"   📄 {doc_id} ({status}): {len(chunks)} chunks from {len(content)} chars")
            
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
        
        archived_count = sum(1 for info in archive_status.values() if info.get('is_archived'))
        current_count = len(archive_status) - archived_count
        print(f"\n📦 Chunking complete:")
        print(f"   Total chunks: {len(ids)}")
        print(f"   Archived documents: {archived_count}")
        print(f"   Current documents: {current_count}")

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
                        print(f"✓ Archived handbook_{handbook_id}")
                        updated_count += 1
                    
                    elif doc_id.startswith('course_'):
                        course_id = doc_id.replace('course_', '')
                        conn.execute("UPDATE Course SET archive_at = NOW() WHERE course_id = %s",
                                    (course_id,))
                        print(f"✓ Archived course_{course_id}")
                        updated_count += 1
            
            if updated_count > 0:
                db.commit()
                print(f"✓ {updated_count} documents archived in database")
            else:
                print("✓ No documents needed archiving")
                
        except Exception as e:
            print(f"✗ Error updating archive status: {e}")
            db.rollback()

    def collect_all_documents(self, conn) -> Tuple[List[str], List[dict], List[str], Dict]:
        """Collect all documents from database and websites with version detection."""
        documents, metadata, ids = [], [], []
        documents_data = []

        try:
            self._process_handbook_data(conn, documents_data)
            self._process_course_data(conn, documents_data)
            self._process_faq_data(conn, documents_data)
        except Exception as e:
            print(f"✗ Error collecting documents: {e}")
            raise

        print("\n🔍 Analyzing document versions...")
        archive_status = self.version_detector.determine_archive_status(documents_data)

        self._chunk_and_store_documents(documents_data, archive_status, documents, metadata, ids)

        try:
            print("🌐 Collecting website data...")
            scraped_data = self.web_scraper.scrape_all_websites(self)
            if scraped_data:
                self.web_scraper.process_scraped_content(scraped_data, documents, metadata, ids, self.text_splitter)
        except Exception as e:
            print(f"✗ Error processing website data: {e}")

        return documents, metadata, ids, archive_status

    def sync_data_to_chromadb(self) -> bool:
        """Main function to sync database data to ChromaDB with full recreation."""
        db = self.get_db_connection()
        if not db:
            return False

        try:
            conn = db.cursor()
            print("✓ Database connection established")
            
            print("\n🧹 Performing collection cleanup...")
            self._cleanup_all_collections()
            
            print("\n🔥 Collecting all current documents from database...")
            documents, metadata, ids, archive_status = self.collect_all_documents(conn)

            if not documents:
                print("⚠️ No documents to sync")
                db.close()
                return False

            print(f"✓ Collected {len(documents)} documents to sync")

            # Update archive status in database
            print("\n📋 Updating archive status in database...")
            self._update_archive_status_in_db(db, archive_status)

            try:
                print(f"🗑️ Attempting to delete collection '{self.collection_name}'...")
                self.client.delete_collection(name=self.collection_name)
                print(f"✓ Successfully deleted old collection '{self.collection_name}'")
            except Exception as e:
                print(f"ℹ️ Collection didn't exist or couldn't be deleted: {e}")

            print(f"🆕 Creating new collection '{self.collection_name}'...")
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"✓ Created new collection '{self.collection_name}'")

            print("📤 Adding documents to new collection...")
            collection.upsert(documents=documents, metadatas=metadata, ids=ids)
            print(f"✓ Successfully added {len(documents)} documents to new collection")

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.update_sync_time(collection, current_time)
            print(f"✓ Sync timestamp updated: {current_time}")

            count = collection.count()
            print(f"✅ Verification: Collection now contains {count} items")

            db.close()
            return True

        except Exception as e:
            print(f"✗ Sync failed: {e}")
            import traceback
            traceback.print_exc()
            if db:
                db.close()
            return False

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

    def debug_collection_state(self):
        """Debug method to see what's in the collection."""
        try:
            collection = self.get_collection()
            all_data = collection.get()
            print("\n🔍 DEBUG - Collection State:")
            print(f"Total items: {len(all_data['ids'])}")

            handbook_ids = [id for id in all_data['ids'] if id.startswith('handbook_')]
            course_ids = [id for id in all_data['ids'] if id.startswith('course_')]
            url_ids = [id for id in all_data['ids'] if id.startswith('url_')]
            faq_ids = [id for id in all_data['ids'] if id.startswith('faq_')]

            print(f"Handbook chunks: {len(handbook_ids)}")
            print(f"Course chunks: {len(course_ids)}")
            print(f"URL chunks: {len(url_ids)}")
            print(f"FAQ chunks: {len(faq_ids)}")

            archived = sum(1 for meta in all_data['metadatas'] if meta.get('is_archived', False))
            current = sum(1 for meta in all_data['metadatas'] if not meta.get('is_archived', True))
            print(f"📦 Archived chunks: {archived}")
            print(f"✓ Current chunks: {current}")

            if all_data['metadatas']:
                print("\n📋 Sample metadata (first 3):")
                for i, meta in enumerate(all_data['metadatas'][:3]):
                    program_id = meta.get('program_id', 'N/A')
                    print(f"  [{i+1}] is_archived={meta.get('is_archived')}, "
                          f"version={meta.get('document_version')}, "
                          f"year={meta.get('revision_year', 'N/A')}, "
                          f"program={program_id}")

            unique_docs = set()
            for doc_id in all_data['ids']:
                base_id = self._extract_base_id(doc_id)
                if base_id:
                    unique_docs.add(base_id)

            print(f"\nUnique documents: {len(unique_docs)}")
            return True
        except Exception as e:
            print(f"✗ Debug failed: {e}")
            return False

    def run_continuous_sync(self):
        """Continuously monitor for updates and sync when needed."""
        print("=" * 60)
        print("TLC Chatmate - Database Sync Service")
        print("=" * 60)

        print("\n[INITIAL SYNC]")
        if self.sync_data_to_chromadb():
            print("✓ Initial sync completed successfully")
            self.debug_collection_state()
        else:
            print("✗ Initial sync failed\n")
            return

        last_sync_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n📊 Monitoring for updates (checking every {self.sync_interval} seconds)...")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                time.sleep(self.sync_interval)
                check_db = self.get_db_connection()
                if not check_db:
                    continue

                try:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking for changes...")

                    if self.event_detector.check_for_updates(check_db, last_sync_time):
                        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚡ CHANGES DETECTED! Recreating entire collection...")
                        check_db.close()
                        if self.sync_data_to_chromadb():
                            last_sync_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            print(f"✓ Collection completely recreated at {last_sync_time}")
                            self.debug_collection_state()
                            print()
                        else:
                            print("✗ Collection recreation failed\n")
                    else:
                        check_db.close()
                except Exception as e:
                    print(f"✗ Error during sync check: {e}")
                    if check_db:
                        check_db.close()

        except KeyboardInterrupt:
            print("\n\n🛑 Stopping sync service...")
            print("=" * 60)


def main():
    synchronizer = KnowledgeRepository()
    synchronizer.run_continuous_sync()


if __name__ == "__main__":
    main()