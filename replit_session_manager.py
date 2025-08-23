"""
Replit-Optimized Session Manager
Stores session data in Replit's Key-Value Store instead of cookies
"""

import os
import json
import uuid
import logging
from typing import Dict, Any, Optional
from flask import session
import requests

class ReplitSessionManager:
    """Session manager that uses Replit's Key-Value Store for data persistence."""
    
    def __init__(self):
        self.db_url = os.environ.get('REPLIT_DB_URL')
        self.enabled = bool(self.db_url)
        if self.enabled:
            logging.info("Replit Key-Value Store available - using optimized session management")
        else:
            logging.warning("Replit DB not available - falling back to Flask sessions")
    
    def get_session_id(self) -> str:
        """Get or create a lightweight session ID for cookie storage."""
        if 'replit_session_id' not in session:
            session['replit_session_id'] = str(uuid.uuid4())
        return session['replit_session_id']
    
    def _get_key(self, data_type: str) -> str:
        """Generate a key for storing specific data type."""
        session_id = self.get_session_id()
        return f"session:{session_id}:{data_type}"
    
    def set_data(self, data_type: str, data: Any) -> bool:
        """Store data in Replit Key-Value Store."""
        if not self.enabled or not self.db_url:
            # Fallback to regular Flask session
            session[data_type] = data
            return True
        
        try:
            key = self._get_key(data_type)
            json_data = json.dumps(data, default=str)
            
            # Check size limit (5MB per value)
            if len(json_data.encode('utf-8')) > 5 * 1024 * 1024:
                logging.error(f"Data too large for Replit DB: {len(json_data)} bytes")
                return False
            
            response = requests.post(self.db_url, data={key: json_data})
            response.raise_for_status()
            
            logging.debug(f"Stored {data_type} in Replit DB ({len(json_data)} bytes)")
            return True
        except Exception as e:
            logging.error(f"Failed to store {data_type} in Replit DB: {e}")
            # Fallback to session
            session[data_type] = data
            return False
    
    def get_data(self, data_type: str, default=None) -> Any:
        """Retrieve data from Replit Key-Value Store."""
        if not self.enabled:
            # Fallback to regular Flask session
            return session.get(data_type, default)
        
        try:
            key = self._get_key(data_type)
            response = requests.get(f"{self.db_url}/{key}")
            
            if response.status_code == 404:
                return default
            
            response.raise_for_status()
            data = json.loads(response.text)
            logging.debug(f"Retrieved {data_type} from Replit DB")
            return data
        except Exception as e:
            logging.error(f"Failed to retrieve {data_type} from Replit DB: {e}")
            # Fallback to session
            return session.get(data_type, default)
    
    def delete_data(self, data_type: str) -> bool:
        """Delete data from Replit Key-Value Store."""
        if not self.enabled:
            # Fallback to regular Flask session
            session.pop(data_type, None)
            return True
        
        try:
            key = self._get_key(data_type)
            response = requests.delete(f"{self.db_url}/{key}")
            # 404 is OK - means already deleted
            if response.status_code not in [200, 404]:
                response.raise_for_status()
            
            logging.debug(f"Deleted {data_type} from Replit DB")
            return True
        except Exception as e:
            logging.error(f"Failed to delete {data_type} from Replit DB: {e}")
            return False
    
    def clear_all_session_data(self) -> bool:
        """Clear all session data for current session."""
        if not self.enabled:
            session.clear()
            return True
        
        try:
            session_id = self.get_session_id()
            # Get all keys with our session prefix
            response = requests.get(f"{self.db_url}?prefix=session:{session_id}:")
            
            if response.status_code == 200:
                keys = response.text.split('\n') if response.text else []
                for key in keys:
                    if key.strip():
                        requests.delete(f"{self.db_url}/{key.strip()}")
            
            # Also clear Flask session
            session.clear()
            logging.info(f"Cleared all session data for {session_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to clear session data: {e}")
            return False
    
    def migrate_from_flask_session(self) -> bool:
        """One-time migration of existing Flask session data to Replit DB."""
        if not self.enabled:
            return True
        
        try:
            migrated_keys = []
            for key, value in session.items():
                if key != 'replit_session_id':  # Don't migrate the session ID itself
                    if self.set_data(key, value):
                        migrated_keys.append(key)
            
            # Remove migrated data from Flask session to reduce cookie size
            for key in migrated_keys:
                session.pop(key, None)
            
            logging.info(f"Migrated {len(migrated_keys)} session keys to Replit DB")
            return True
        except Exception as e:
            logging.error(f"Failed to migrate session data: {e}")
            return False

# Global instance
replit_session = ReplitSessionManager()

# Convenience functions for game data
def set_player_data(player_data: Dict[str, Any]) -> bool:
    """Store player data optimally."""
    return replit_session.set_data('player', player_data)

def get_player_data(default=None) -> Dict[str, Any]:
    """Get player data."""
    return replit_session.get_data('player', default or {})

def set_game_state(state_data: Dict[str, Any]) -> bool:
    """Store game state (resources, mission, etc.)."""
    return replit_session.set_data('game_state', state_data)

def get_game_state(default=None) -> Dict[str, Any]:
    """Get game state."""
    return replit_session.get_data('game_state', default or {})

def set_story_data(story_data: str) -> bool:
    """Store story content."""
    # For large story data, we might need to chunk it
    if len(story_data.encode('utf-8')) > 4 * 1024 * 1024:  # 4MB threshold
        # Split large story into chunks
        chunk_size = 3 * 1024 * 1024  # 3MB chunks
        chunks = [story_data[i:i+chunk_size] for i in range(0, len(story_data), chunk_size)]
        
        success = True
        for i, chunk in enumerate(chunks):
            chunk_key = f"story_chunk_{i}"
            success = success and replit_session.set_data(chunk_key, chunk)
        
        # Store chunk metadata
        metadata = {"total_chunks": len(chunks), "total_length": len(story_data)}
        success = success and replit_session.set_data('story_metadata', metadata)
        
        return success
    else:
        return replit_session.set_data('story', story_data)

def get_story_data(default="") -> str:
    """Get story content, handling chunked data."""
    # First try to get non-chunked story
    story = replit_session.get_data('story')
    if story is not None:
        return story
    
    # Try to get chunked story
    metadata = replit_session.get_data('story_metadata')
    if metadata and 'total_chunks' in metadata:
        chunks = []
        for i in range(metadata['total_chunks']):
            chunk = replit_session.get_data(f'story_chunk_{i}', "")
            chunks.append(chunk)
        
        return "".join(chunks)
    
    return default