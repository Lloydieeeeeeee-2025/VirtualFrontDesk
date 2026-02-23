from typing import Set, Dict, List


class EventDetection:
    """Detects changes (insert, update, delete) in the database since last sync."""

    def __init__(self, knowledge_repo):
        self.repo = knowledge_repo
        self.last_processed_ids: Set[str] = set()

    def get_current_document_ids(self) -> Set[str]:
        """Get all current (non-archived) document IDs from the database."""
        current_ids = set()
        db = self.repo.get_db_connection()
        if not db:
            return current_ids

        try:
            conn = db.cursor()

            conn.execute("SELECT handbook_id FROM handbook WHERE archive_at IS NULL")
            for (handbook_id,) in conn.fetchall():
                if handbook_id:
                    current_ids.add(f"handbook_{handbook_id}")

            conn.execute("SELECT course_id FROM course WHERE archive_at IS NULL")
            for (course_id,) in conn.fetchall():
                if course_id:
                    current_ids.add(f"course_{course_id}")

            conn.execute("SELECT link_url FROM url")
            for (url,) in conn.fetchall():
                if url:
                    url_id = (
                        url.replace('https://', '').replace('http://', '')
                           .replace('/', '_').replace('.', '_').rstrip('_')
                    )
                    current_ids.add(f"url_{url_id}")

            conn.execute("SELECT faq_id FROM faqs")
            for (faq_id,) in conn.fetchall():
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

            conn.execute("""
                SELECT 'handbook' AS type, handbook_id AS id FROM handbook
                WHERE updated_at > %s AND archive_at IS NULL
                UNION ALL
                SELECT 'course', course_id FROM course
                WHERE updated_at > %s AND archive_at IS NULL
                UNION ALL
                SELECT 'url', link_url FROM url
                WHERE updated_at > %s
                UNION ALL
                SELECT 'faq', faq_id FROM faqs
                WHERE updated_at > %s
            """, (last_sync_time, last_sync_time, last_sync_time, last_sync_time))

            for doc_type, doc_id in conn.fetchall():
                formatted_id = self._format_doc_id(doc_type, doc_id)
                if formatted_id not in self.last_processed_ids:
                    changes['inserted'].append(formatted_id)
                else:
                    changes['updated'].append(formatted_id)

            current_ids = self.get_current_document_ids()
            changes['deleted'] = list(self.last_processed_ids - current_ids)
            self.last_processed_ids = current_ids

            total = sum(len(v) for v in changes.values())
            if total > 0:
                print(
                    f"Changes detected: {len(changes['inserted'])} inserted, "
                    f"{len(changes['updated'])} updated, {len(changes['deleted'])} deleted"
                )
            return changes

        except Exception as e:
            print(f"Error detecting changes: {e}")
            return changes

    def check_for_updates(self, db, last_sync_time: str) -> bool:
        """
        Check if any records have been updated, inserted, or deleted since last sync.

        False-positive guard:  last_processed_ids must be seeded before calling
        this method (KnowledgeRepository does this after every sync and on the
        first call to check_updates_available).  Without seeding, the deletion
        check always reports every document as deleted on a fresh process start.
        """
        try:
            conn = db.cursor()

            conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT handbook_id FROM handbook
                    WHERE updated_at > %s AND archive_at IS NULL
                    UNION ALL
                    SELECT course_id FROM course
                    WHERE updated_at > %s AND archive_at IS NULL
                    UNION ALL
                    SELECT link_url FROM url
                    WHERE updated_at > %s
                    UNION ALL
                    SELECT faq_id FROM faqs
                    WHERE updated_at > %s
                ) AS updates
            """, (last_sync_time, last_sync_time, last_sync_time, last_sync_time))

            result = conn.fetchone()
            update_count = result[0] if result else 0

            if update_count > 0:
                print(f"Updates detected: {update_count} records modified since {last_sync_time}")
                return True

            # Check for deletions using in-memory baseline.
            current_doc_ids = self.get_current_document_ids()
            deleted_ids = self.last_processed_ids - current_doc_ids
            if deleted_ids:
                print(f"Deletions detected: {len(deleted_ids)} documents removed")
                return True

            return False

        except Exception as e:
            print(f"Error checking for updates: {e}")
            return True

    @staticmethod
    def _format_doc_id(doc_type: str, doc_id: str) -> str:
        """Format document ID based on type."""
        if doc_type == 'url':
            url_id = (
                doc_id.replace('https://', '').replace('http://', '')
                      .replace('/', '_').replace('.', '_').rstrip('_')
            )
            return f"url_{url_id}"
        return f"{doc_type}_{doc_id}"