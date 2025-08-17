"""
Enhanced Session Management Module
Improved session handling, cleanup, and size monitoring
"""

import logging
import sys
from flask import session
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from config import SESSION_CONFIG


class SessionManager:
    """Enhanced session management with automatic cleanup and monitoring."""
    
    def __init__(self):
        self.config = SESSION_CONFIG
        self.cleanup_counter = 0
        
    def initialize_session(self, player_data: Dict[str, Any]) -> None:
        """Initialize a new game session with proper structure."""
        session.clear()
        session.permanent = True
        
        # Core player data
        session["player"] = player_data
        session["game_start_time"] = datetime.now().isoformat()
        session["turn_count"] = 0
        session["session_version"] = "2.0"  # For future compatibility
        
        # Game state
        session["story_history"] = []
        session["current_mission"] = {}
        session["achievements_unlocked"] = []
        session["resources"] = self._get_default_resources()
        
        # Performance tracking
        session["last_cleanup"] = datetime.now().isoformat()
        session["cleanup_count"] = 0
        
        logging.info(f"New session initialized for player: {player_data.get('name', 'Unknown')}")
    
    def _get_default_resources(self) -> Dict[str, int]:
        """Get default starting resources for new players."""
        return {
            "ammo": 120,
            "medkits": 3,
            "grenades": 2,
            "food": 5,
            "intel_points": 0
        }
    
    def update_session_data(self, updates: Dict[str, Any]) -> None:
        """Safely update session data with validation."""
        for key, value in updates.items():
            if key in ["player", "current_mission", "resources"]:
                # Validate critical data
                if self._validate_session_data(key, value):
                    session[key] = value
                else:
                    logging.warning(f"Invalid session data rejected for key: {key}")
            else:
                session[key] = value
        
        # Increment turn counter for auto-cleanup
        self.cleanup_counter += 1
        if self.cleanup_counter >= self.config["auto_cleanup_interval"]:
            self.auto_cleanup()
            self.cleanup_counter = 0
    
    def _validate_session_data(self, key: str, value: Any) -> bool:
        """Validate critical session data before storing."""
        if key == "player":
            required_fields = ["name", "rank", "class", "weapon"]
            if not all(field in value for field in required_fields):
                return False
        elif key == "resources":
            if not isinstance(value, dict):
                return False
            # Check for negative values
            if any(v < 0 for v in value.values() if isinstance(v, (int, float))):
                return False
        elif key == "current_mission":
            if not isinstance(value, dict):
                return False
        
        return True
    
    def add_story_entry(self, story_text: str, choices: Optional[List[str]] = None) -> None:
        """Add story entry with automatic history management."""
        if "story_history" not in session:
            session["story_history"] = []
        
        story_entry = {
            "text": story_text,
            "choices": choices or [],
            "timestamp": datetime.now().isoformat(),
            "turn": session.get("turn_count", 0)
        }
        
        session["story_history"].append(story_entry)
        
        # Auto-compress if history too long
        if len(session["story_history"]) > self.config["max_story_history"]:
            self._compress_story_history()
    
    def _compress_story_history(self) -> None:
        """Compress story history to manage memory."""
        history = session["story_history"]
        
        # Keep first entry (mission start) and recent entries
        compressed_history = []
        if history:
            compressed_history.append(history[0])  # Mission start
            compressed_history.extend(history[-5:])  # Recent entries
        
        # Remove duplicates while preserving order
        seen_texts = set()
        final_history = []
        for entry in compressed_history:
            if entry["text"] not in seen_texts:
                seen_texts.add(entry["text"])
                final_history.append(entry)
        
        session["story_history"] = final_history
        session["story_compressed"] = True
        session["compression_time"] = datetime.now().isoformat()
        
        logging.info(f"Story history compressed from {len(history)} to {len(final_history)} entries")
    
    def auto_cleanup(self) -> None:
        """Perform automatic session cleanup."""
        initial_size = self.get_session_size()
        
        # Remove temporary data
        temp_keys = [
            "temp_story", "new_content", "error_state", "debug_info",
            "last_ai_request", "temp_combat_data", "validation_errors"
        ]
        
        removed_count = 0
        for key in temp_keys:
            if key in session:
                session.pop(key)
                removed_count += 1
        
        # Compress story if needed
        if len(session.get("story_history", [])) > 6:
            self._compress_story_history()
        
        # Update cleanup tracking
        session["last_cleanup"] = datetime.now().isoformat()
        session["cleanup_count"] = session.get("cleanup_count", 0) + 1
        
        final_size = self.get_session_size()
        logging.debug(f"Auto-cleanup completed: {removed_count} temp items removed, "
                     f"size reduced from {initial_size} to {final_size} bytes")
    
    def get_session_size(self) -> int:
        """Get current session size in bytes."""
        try:
            return sys.getsizeof(str(dict(session)))
        except Exception:
            return 0
    
    def get_session_health(self) -> Dict[str, Any]:
        """Get detailed session health information."""
        size = self.get_session_size()
        max_size = self.config["max_session_size_bytes"]
        
        return {
            "size_bytes": size,
            "size_percentage": (size / max_size) * 100,
            "story_entries": len(session.get("story_history", [])),
            "turn_count": session.get("turn_count", 0),
            "cleanup_count": session.get("cleanup_count", 0),
            "last_cleanup": session.get("last_cleanup"),
            "health_status": self._get_health_status(size, max_size)
        }
    
    def _get_health_status(self, current_size: int, max_size: int) -> str:
        """Get session health status."""
        percentage = (current_size / max_size) * 100
        
        if percentage < 50:
            return "healthy"
        elif percentage < 75:
            return "warning"
        else:
            return "critical"
    
    def export_session_data(self) -> Dict[str, Any]:
        """Export session data for backup or analysis."""
        return {
            "player": session.get("player", {}),
            "story_history": session.get("story_history", []),
            "achievements": session.get("achievements_unlocked", []),
            "resources": session.get("resources", {}),
            "stats": {
                "turn_count": session.get("turn_count", 0),
                "session_health": self.get_session_health()
            }
        }
    
    def validate_session(self) -> Optional[str]:
        """Validate session integrity and return error message if invalid."""
        if "player" not in session:
            return "Player data not found"
        
        player = session.get("player", {})
        required_fields = ["name", "rank", "class", "weapon"]
        
        for field in required_fields:
            if not player.get(field):
                return f"Missing player field: {field}"
        
        # Check session size
        size = self.get_session_size()
        if size > self.config["max_session_size_bytes"]:
            logging.warning(f"Session size critical: {size} bytes")
            self.auto_cleanup()
        
        return None


# Global session manager instance
session_manager = SessionManager()