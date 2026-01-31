import io
import time
import base64
from typing import List, Tuple
from datetime import datetime
from dotenv import load_dotenv
from dbconnector.db import tlcchatmate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ChromaDBService import ChromaDBService
from pypdf import PdfReader
from bs4 import BeautifulSoup
from EventDetection import EventDetection
from WebScraper import WebScraper
from VersionDetector import VersionDetector


class KnowledgeRepository(ChromaDBService):
    """Handles synchronization between database and ChromaDB."""

    def __init__(self):
        load_dotenv()
        super().__init__()
        self.client = self.client
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

    def get_db_connection(self):
        try:
            return tlcchatmate()
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return None

    def decode_pdf_bytes(self, pdf_data):
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

    def _process_handbook_data(self, conn, documents_data: List[dict]):
        """Process handbook PDF data and collect for version detection."""
        conn.execute("SELECT handbook_id, handbook_document, handbook_name, updated_at FROM Handbook")
        for row in conn.fetchall():
            handbook_id, handbook_document, handbook_name, updated_at = row
            if handbook_document is None:
                print(f"⚠ Handbook {handbook_id} has no document content, skipping...")
                continue

            handbook_bytes = self.decode_pdf_bytes(handbook_document)
            content = ""
            if handbook_bytes and isinstance(handbook_bytes, bytes):
                try:
                    reader = PdfReader(io.BytesIO(handbook_bytes))
                    content = "\n".join(page.extract_text() or "" for page in reader.pages)
                except Exception as e:
                    print(f"✗ Error extracting PDF {handbook_id}: {e}")
                    continue

            if not content.strip():
                print(f"⚠ Handbook {handbook_id} has no extractable text content, skipping...")
                continue

            documents_data.append({
                'id': f"handbook_{handbook_id}",
                'name': handbook_name or "",
                'content': content,
                'type': 'handbook',
                'updated_at': updated_at.strftime('%Y-%m-%d %H:%M:%S') if updated_at else ""
            })

        print(f"✓ Collected {len([d for d in documents_data if d['type'] == 'handbook'])} handbooks")

    def _process_course_data(self, conn, documents_data: List[dict]):
        """Process course PDF data and collect for version detection."""
        conn.execute("SELECT course_id, course_document, document_name, updated_at FROM Course")
        for row in conn.fetchall():
            course_id, course_document, document_name, updated_at = row
            if course_document is None:
                print(f"⚠ Course {course_id} has no document content, skipping...")
                continue

            course_bytes = self.decode_pdf_bytes(course_document)
            content = ""
            if course_bytes and isinstance(course_bytes, bytes):
                try:
                    reader = PdfReader(io.BytesIO(course_bytes))
                    content = "\n".join(page.extract_text() or "" for page in reader.pages)
                except Exception as e:
                    print(f"✗ Error extracting PDF {course_id}: {e}")
                    continue

            if not content.strip():
                print(f"⚠ Course {course_id} has no extractable text content, skipping...")
                continue

            documents_data.append({
                'id': f"course_{course_id}",
                'name': document_name or "",
                'content': content,
                'type': 'course',
                'updated_at': updated_at.strftime('%Y-%m-%d %H:%M:%S') if updated_at else ""
            })

        print(f"✓ Collected {len([d for d in documents_data if d['type'] == 'course'])} courses")

    def _chunk_and_store_documents(self, documents_data: List[dict], archive_status: dict, 
                                   documents: List[str], metadata: List[dict], ids: List[str]):
        """Chunk documents and add archive metadata - CRITICAL: Ensure is_archived is always set."""
        for doc_data in documents_data:
            doc_id = doc_data['id']
            content = doc_data['content']
            is_archived = archive_status.get(doc_id, False)
            
            # CRITICAL: Extract revision year for metadata
            revision_info = self.version_detector.extract_all_revision_info(content)
            revision_year = revision_info.get('year', None)
            
            chunks = self.text_splitter.split_text(content)
            for idx, chunk in enumerate(chunks):
                documents.append(chunk)
                chunk_id = f"{doc_id}_chunk_{idx}"
                ids.append(chunk_id)
                
                # CRITICAL: Always set is_archived as boolean, never None
                meta = {
                    "data_type": doc_data['type'],
                    "updated_at": doc_data['updated_at'],
                    "chunk_index": idx,
                    "is_archived": bool(is_archived),  # Ensure boolean
                    "document_version": "archived" if is_archived else "current"
                }
                
                # Add revision year if found
                if revision_year:
                    meta["revision_year"] = revision_year
                
                if doc_data['type'] == 'handbook':
                    meta["handbook_id"] = doc_id.replace("handbook_", "")
                    meta["handbook_name"] = doc_data['name']
                elif doc_data['type'] == 'course':
                    meta["course_id"] = doc_id.replace("course_", "")
                    meta["document_name"] = doc_data['name']
                
                metadata.append(meta)
        
        archived_count = sum(1 for status in archive_status.values() if status)
        current_count = len(archive_status) - archived_count
        print(f"📦 Archived: {archived_count} documents, Current: {current_count} documents")

    def collect_all_documents(self, conn) -> Tuple[List[str], List[dict], List[str]]:
        """Collect all documents from database and websites with version detection."""
        documents, metadata, ids = [], [], []
        documents_data = []

        try:
            self._process_handbook_data(conn, documents_data)
            self._process_course_data(conn, documents_data)
        except Exception as e:
            print(f"✗ Error collecting documents: {e}")
            raise

        print("\n🔍 Analyzing document versions...")
        archive_status = self.version_detector.determine_archive_status(documents_data)

        self._chunk_and_store_documents(documents_data, archive_status, documents, metadata, ids)

        try:
            print("🕸️ Collecting website data...")
            scraped_data = self.web_scraper.scrape_all_websites()
            if scraped_data:
                self.web_scraper.process_scraped_content(scraped_data, documents, metadata, ids, self.text_splitter)
        except Exception as e:
            print(f"✗ Error processing website data: {e}")

        return documents, metadata, ids

    def sync_data_to_chromadb(self) -> bool:
        """Main function to sync database data to ChromaDB - FULL RECREATION."""
        db = self.get_db_connection()
        if not db:
            return False

        try:
            conn = db.cursor()
            print("✓ Database connection established")
            print("🔥 Collecting all current documents from database...")
            documents, metadata, ids = self.collect_all_documents(conn)

            if not documents:
                print("⚠ No documents to sync")
                db.close()
                return False

            print(f"✓ Collected {len(documents)} documents to sync")

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

            print(f"Handbook chunks: {len(handbook_ids)}")
            print(f"Course chunks: {len(course_ids)}")
            print(f"URL chunks: {len(url_ids)}")

            archived = sum(1 for meta in all_data['metadatas'] if meta.get('is_archived', False))
            current = sum(1 for meta in all_data['metadatas'] if not meta.get('is_archived', True))
            print(f"📦 Archived chunks: {archived}")
            print(f"✓ Current chunks: {current}")

            # Show sample metadata
            if all_data['metadatas']:
                print("\n📋 Sample metadata (first 3):")
                for i, meta in enumerate(all_data['metadatas'][:3]):
                    print(f"  [{i+1}] is_archived={meta.get('is_archived')}, "
                          f"version={meta.get('document_version')}, "
                          f"year={meta.get('revision_year', 'N/A')}")

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
                    self.debug_collection_state()

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