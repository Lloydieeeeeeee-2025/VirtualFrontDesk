import threading
from typing import Dict, List, Optional
from datetime import datetime
import uuid


class SessionManager:
    """
    Manages isolated user sessions with thread-safe conversation history.
    Prevents context bleeding between users/devices.
    """

    def __init__(self, max_history_per_session: int = 4):
        """
        Args:
            max_history_per_session: Maximum conversation exchanges to keep per session
        """
        self._sessions: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self.max_history_per_session = max_history_per_session
        self.max_messages = max_history_per_session * 2

    def create_session(self, session_id: str = None, user_id: str = None) -> str:
        """
        Create a new isolated session.
        IMPORTANT: Each session_id must be UNIQUE per device/browser
        
        Args:
            session_id: Optional custom session ID, generates UUID if not provided
            user_id: Optional user identifier for tracking
            
        Returns:
            The session ID
        """
        if not session_id:
            session_id = f"session_{uuid.uuid4()}"

        with self._lock:
            if session_id in self._sessions:
                print(f"⚠️ Recreating session: {session_id}")
            
            self._sessions[session_id] = {
                'history': [],
                'user_id': user_id,
                'created_at': datetime.now(),
                'last_accessed': datetime.now(),
                'metadata': {}
            }
            print(f"✓ Session created: {session_id} (User: {user_id or 'anonymous'})")
            return session_id

    def get_session_history(self, session_id: str) -> List[dict]:
        """
        Get conversation history for a specific session.
        Returns empty list if session doesn't exist.
        
        Args:
            session_id: The session ID
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        with self._lock:
            if session_id not in self._sessions:
                print(f"⚠️ Session not found: {session_id}")
                return []

            self._sessions[session_id]['last_accessed'] = datetime.now()
            return self._sessions[session_id]['history'].copy()

    def add_to_history(self, session_id: str, role: str, content: str) -> bool:
        """
        Add a message to a session's history.
        
        Args:
            session_id: The session ID
            role: 'user' or 'assistant'
            content: Message content
            
        Returns:
            True if added successfully, False if session not found
        """
        with self._lock:
            if session_id not in self._sessions:
                print(f"⚠️ Cannot add to history: session not found {session_id}")
                return False

            self._sessions[session_id]['history'].append({
                'role': role,
                'content': content
            })
            self._sessions[session_id]['last_accessed'] = datetime.now()

            if len(self._sessions[session_id]['history']) > self.max_messages:
                self._sessions[session_id]['history'] = self._sessions[session_id]['history'][-self.max_messages:]

            return True

    def update_history(self, session_id: str, history: List[dict]) -> bool:
        """
        Bulk update conversation history for a session.
        CRITICAL: This replaces the entire history
        
        Args:
            session_id: The session ID
            history: List of message dicts
            
        Returns:
            True if updated successfully, False if session not found
        """
        with self._lock:
            if session_id not in self._sessions:
                print(f"⚠️ Cannot update history: session not found {session_id}")
                return False

            trimmed_history = history[-self.max_messages:] if history else []
            self._sessions[session_id]['history'] = trimmed_history
            self._sessions[session_id]['last_accessed'] = datetime.now()
            return True

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        with self._lock:
            return session_id in self._sessions

    def get_all_sessions(self) -> List[str]:
        """Get list of all active session IDs."""
        with self._lock:
            return list(self._sessions.keys())

    def get_session_metadata(self, session_id: str) -> Optional[Dict]:
        """Get metadata for a session."""
        with self._lock:
            if session_id not in self._sessions:
                return None
            session = self._sessions[session_id]
            return {
                'user_id': session['user_id'],
                'created_at': session['created_at'],
                'last_accessed': session['last_accessed'],
                'history_length': len(session['history'])
            }

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                print(f"✓ Session deleted: {session_id}")
                return True
            return False

    def clear_expired_sessions(self, timeout_seconds: int = 3600) -> int:
        """
        Remove sessions older than timeout (default 1 hour).
        
        Args:
            timeout_seconds: Session inactivity timeout
            
        Returns:
            Number of sessions deleted
        """
        with self._lock:
            now = datetime.now()
            expired = []

            for session_id, session_data in self._sessions.items():
                elapsed = (now - session_data['last_accessed']).total_seconds()
                if elapsed > timeout_seconds:
                    expired.append(session_id)

            for session_id in expired:
                del self._sessions[session_id]

            if expired:
                print(f"🗑️ Cleaned up {len(expired)} expired sessions")

            return len(expired)