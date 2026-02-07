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
            # CRITICAL: Always create fresh session
            # Clear any existing session with this ID first
            if session_id in self._sessions:
                print(f"⚠ Recreating session: {session_id} (clearing previous data)")
            
            self._sessions[session_id] = {
                'history': [],  # Always start empty
                'user_id': user_id,
                'created_at': datetime.now(),
                'last_accessed': datetime.now(),
                'metadata': {}
            }
            print(f"✓ Session created: {session_id} (User: {user_id or 'anonymous'}, history: EMPTY)")
            return session_id

    def get_session_history(self, session_id: str) -> List[dict]:
        """
        Get conversation history for a specific session.
        Returns EMPTY list if session doesn't exist (not found).
        
        Args:
            session_id: The session ID
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        with self._lock:
            if session_id not in self._sessions:
                print(f"⚠ Session not found: {session_id} - returning EMPTY history")
                return []

            self._sessions[session_id]['last_accessed'] = datetime.now()
            history_copy = self._sessions[session_id]['history'].copy()
            print(f"✓ Retrieved history for {session_id}: {len(history_copy)} messages")
            return history_copy

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
                print(f"⚠ Cannot add to history: session not found {session_id}")
                return False

            self._sessions[session_id]['history'].append({
                'role': role,
                'content': content
            })
            self._sessions[session_id]['last_accessed'] = datetime.now()

            # Trim history to max size (keep last N exchanges = 2N messages)
            max_messages = self.max_history_per_session * 2
            if len(self._sessions[session_id]['history']) > max_messages:
                self._sessions[session_id]['history'] = self._sessions[session_id]['history'][-max_messages:]

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
                print(f"⚠ Cannot update history: session not found {session_id}")
                return False

            # Keep only max messages
            max_messages = self.max_history_per_session * 2
            trimmed_history = history[-max_messages:] if history else []
            self._sessions[session_id]['history'] = trimmed_history
            self._sessions[session_id]['last_accessed'] = datetime.now()
            print(f"✓ Updated history for {session_id}: {len(trimmed_history)} messages")
            return True

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        with self._lock:
            exists = session_id in self._sessions
            if not exists:
                print(f"✗ Session does not exist: {session_id}")
            return exists

    def get_all_sessions(self) -> List[str]:
        """Get list of all active session IDs."""
        with self._lock:
            return list(self._sessions.keys())

    def get_session_metadata(self, session_id: str) -> Optional[Dict]:
        """Get metadata for a session."""
        with self._lock:
            if session_id not in self._sessions:
                return None
            return {
                'user_id': self._sessions[session_id]['user_id'],
                'created_at': self._sessions[session_id]['created_at'],
                'last_accessed': self._sessions[session_id]['last_accessed'],
                'history_length': len(self._sessions[session_id]['history'])
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

    def debug_session_state(self, session_id: str = None) -> None:
        """Debug: Print session state for debugging."""
        with self._lock:
            if session_id:
                if session_id in self._sessions:
                    session = self._sessions[session_id]
                    print(f"\n🔍 DEBUG Session: {session_id}")
                    print(f"  User: {session['user_id']}")
                    print(f"  Created: {session['created_at']}")
                    print(f"  History length: {len(session['history'])}")
                    print(f"  Messages: {[{m['role']} for m in session['history'][-4:]]}")
                else:
                    print(f"✗ Session {session_id} not found")
            else:
                print(f"\n🔍 DEBUG All Sessions ({len(self._sessions)} total)")
                for sid, session in self._sessions.items():
                    print(f"  {sid}: {len(session['history'])} messages, user={session['user_id']}")