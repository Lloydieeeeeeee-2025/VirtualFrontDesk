from typing import Set, Dict, List


class EventDetection:
    """Detects changes (insert, update, delete) in the database since last sync."""

    def __init__(self, knowledge_repo):
        self.repo = knowledge_repo
        self.last_processed_ids: Set[str] = set()

    def get_current_document_ids(self) -> Set[str]:
        """Get all current document IDs from the database for comparison."""
        current_ids = set()
        db = self.repo.get_db_connection()
        if not db:
            return current_ids

        try:
            conn = db.cursor()

            conn.execute("SELECT handbook_id FROM Handbook WHERE archive_at IS NULL")
            for row in conn.fetchall():
                handbook_id = row[0]
                if handbook_id:
                    current_ids.add(f"handbook_{handbook_id}")

            conn.execute("SELECT course_id FROM Course WHERE archive_at IS NULL")
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
            return current_ids

        except Exception as e:
            print(f"Error getting current document IDs: {e}")
            if db:
                db.close()
            return set()

    def get_changed_documents(self, db, last_sync_time: str) -> Dict[str, List[str]]:
        """
        Get incremental changes since last sync.
        Returns: {'inserted': [...], 'updated': [...], 'deleted': [...]}
        """
        changes = {'inserted': [], 'updated': [], 'deleted': []}
        
        try:
            conn = db.cursor()

            # Check for updated/inserted records
            conn.execute("""
                SELECT 'handbook' as type, handbook_id as id FROM Handbook 
                WHERE updated_at > %s AND archive_at IS NULL
                UNION ALL
                SELECT 'course', course_id FROM Course 
                WHERE updated_at > %s AND archive_at IS NULL
                UNION ALL
                SELECT 'url', link_url FROM URL 
                WHERE updated_at > %s
                UNION ALL
                SELECT 'faq', faq_id FROM faqs 
                WHERE updated_at > %s
            """, (last_sync_time, last_sync_time, last_sync_time, last_sync_time))

            for row in conn.fetchall():
                doc_type, doc_id = row[0], row[1]
                formatted_id = self._format_doc_id(doc_type, doc_id)
                if formatted_id not in self.last_processed_ids:
                    changes['inserted'].append(formatted_id)
                else:
                    changes['updated'].append(formatted_id)

            # Check for deletions (including archived documents)
            current_ids = self.get_current_document_ids()
            deleted = self.last_processed_ids - current_ids
            changes['deleted'] = list(deleted)

            self.last_processed_ids = current_ids

            total_changes = len(changes['inserted']) + len(changes['updated']) + len(changes['deleted'])
            if total_changes > 0:
                print(f"Changes detected: {len(changes['inserted'])} inserted, "
                      f"{len(changes['updated'])} updated, {len(changes['deleted'])} deleted")
                return changes
            
            print("No changes detected")
            return changes

        except Exception as e:
            print(f"Error detecting changes: {e}")
            return changes

    def check_for_updates(self, db, last_sync_time: str) -> bool:
        """Check if any records have been updated, inserted, or deleted since last sync."""
        try:
            conn = db.cursor()

            # Check for updates
            conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT handbook_id, updated_at FROM Handbook 
                    WHERE updated_at > %s AND archive_at IS NULL
                    UNION ALL
                    SELECT course_id, updated_at FROM Course 
                    WHERE updated_at > %s AND archive_at IS NULL
                    UNION ALL
                    SELECT link_url, updated_at FROM URL 
                    WHERE updated_at > %s
                    UNION ALL
                    SELECT faq_id, updated_at FROM faqs 
                    WHERE updated_at > %s
                ) AS updates
            """, (last_sync_time, last_sync_time, last_sync_time, last_sync_time))

            update_result = conn.fetchone()
            has_updates = update_result[0] > 0 if update_result else False

            if has_updates:
                print(f"Updates detected: {update_result[0]} records modified since {last_sync_time}")
                return True

            # Check for deletions (including archived documents)
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
                    print(f"Deletions detected: {len(deleted_ids)} documents removed")
                    return True

            print(f"No changes detected (Last sync: {last_sync_time})")
            return False

        except Exception as e:
            print(f"Error checking for updates: {e}")
            return True

    @staticmethod
    def _format_doc_id(doc_type: str, doc_id: str) -> str:
        """Format document ID based on type."""
        if doc_type == 'url':
            url_id = doc_id.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
            url_id = url_id.rstrip('_')
            return f"url_{url_id}"
        return f"{doc_type}_{doc_id}"