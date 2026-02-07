from typing import Set
from datetime import datetime


class EventDetection:
    """Detects changes (insert, update, delete) in the database since last sync."""

    def __init__(self, knowledge_repo):
        self.repo = knowledge_repo

    def get_current_document_ids(self) -> Set[str]:
        """Get all current document IDs from the database for comparison."""
        current_ids = set()
        db = self.repo.get_db_connection()
        if not db:
            return current_ids

        try:
            conn = db.cursor()

            conn.execute("SELECT handbook_id FROM Handbook")
            for row in conn.fetchall():
                handbook_id = row[0]
                if handbook_id:
                    current_ids.add(f"handbook_{handbook_id}")

            conn.execute("SELECT course_id FROM Course")
            for row in conn.fetchall():
                course_id = row[0]
                if course_id:
                    current_ids.add(f"course_{course_id}")

            conn.execute("SELECT link_url FROM URL")
            for row in conn.fetchall():
                url = row[0]
                if url:
                    url_id = url.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
                    url_id = url_id.rstrip('_')
                    current_ids.add(f"url_{url_id}")

            conn.execute("SELECT faq_id FROM faqs")
            for row in conn.fetchall():
                faq_id = row[0]
                if faq_id:
                    current_ids.add(f"faq_{faq_id}")

            db.close()
            print(f"✓ Collected {len(current_ids)} current document IDs from database")
            return current_ids

        except Exception as e:
            print(f"✗ Error getting current document IDs: {e}")
            if db:
                db.close()
            return set()

    def check_for_updates(self, db, last_sync_time: str) -> bool:
        """Check if any records have been updated or deleted since last sync."""
        try:
            conn = db.cursor()

            conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT handbook_id, updated_at FROM Handbook WHERE updated_at > %s
                    UNION ALL
                    SELECT course_id, updated_at FROM Course WHERE updated_at > %s
                    UNION ALL
                    SELECT link_url, updated_at FROM URL WHERE updated_at > %s
                    UNION ALL
                    SELECT faq_id, updated_at FROM faqs WHERE updated_at > %s
                ) AS updates
            """, (last_sync_time, last_sync_time, last_sync_time, last_sync_time))

            update_result = conn.fetchone()
            has_updates = update_result[0] > 0 if update_result else False

            if has_updates:
                print(f"🔔 Updates detected: {update_result[0]} records modified since {last_sync_time}")
                return True

            print("🔔 Checking for deletions...")
            current_doc_ids = self.get_current_document_ids()

            collection = self.repo.get_collection()
            existing_data = collection.get()
            existing_ids = existing_data.get('ids', [])

            chromadb_base_ids = set()
            for existing_id in existing_ids:
                if existing_id.startswith('_sync_'):
                    continue
                base_id = self.repo._extract_base_id(existing_id)
                if base_id:
                    chromadb_base_ids.add(base_id)

            if chromadb_base_ids:
                deleted_ids = chromadb_base_ids - current_doc_ids
                if deleted_ids:
                    print(f"🗑️  Deletions detected: {len(deleted_ids)} documents removed from database")
                    print(f"   Deleted IDs: {list(deleted_ids)[:5]}...")
                    return True

            conn.execute("SELECT COUNT(*) FROM Handbook")
            handbook_count = conn.fetchone()[0]
            conn.execute("SELECT COUNT(*) FROM Course")
            course_count = conn.fetchone()[0]
            conn.execute("SELECT COUNT(*) FROM URL")
            url_count = conn.fetchone()[0]
            conn.execute("SELECT COUNT(*) FROM faqs")
            faq_count = conn.fetchone()[0]
            total_db_records = handbook_count + course_count + url_count + faq_count

            unique_chroma_docs = len(chromadb_base_ids)

            if total_db_records != unique_chroma_docs:
                print(f"🔔 Count mismatch: DB has {total_db_records} records, ChromaDB has {unique_chroma_docs} unique documents")
                return True

            print(f"✓ No changes detected (Last sync: {last_sync_time})")
            return False

        except Exception as e:
            print(f"✗ Error checking for updates: {e}")
            return True