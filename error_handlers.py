"""
Error Handling Module
Centralized error handling and recovery mechanisms
"""

import logging
from flask import session, redirect, url_for, render_template, jsonify
from typing import Dict, Any, Optional

def handle_session_error(error: Exception, fallback_route: str = "index") -> str:
    """Handle session-related errors with graceful recovery."""
    logging.error(f"Session error: {error}")
    
    # Clear problematic session data
    session.clear()
    
    # Redirect to safe state
    return redirect(url_for(fallback_route))

def handle_database_error(error: Exception, operation: str = "database operation") -> Dict[str, Any]:
    """Handle database errors with appropriate fallbacks."""
    logging.error(f"Database error in {operation}: {error}")
    
    return {
        "success": False,
        "error": f"Data storage temporarily unavailable",
        "fallback": True,
        "operation": operation
    }

def handle_ai_error(error: Exception, fallback_content: str = None) -> str:
    """Handle AI service errors with fallback content."""
    logging.warning(f"AI service error: {error}")
    
    if fallback_content:
        return fallback_content
    
    # Generic fallback
    return "The mission continues. Make your next tactical decision carefully."

def validate_player_session() -> Optional[str]:
    """Validate player session and return error message if invalid."""
    if "player" not in session:
        return "Player data not found. Please create a new character."
    
    player = session.get("player", {})
    required_fields = ["name", "rank", "class", "weapon"]
    
    for field in required_fields:
        if not player.get(field):
            return f"Invalid player data: missing {field}. Please recreate character."
    
    return None

def safe_session_get(key: str, default: Any = None, validate_type: type = None) -> Any:
    """Safely get session data with type validation."""
    try:
        value = session.get(key, default)
        
        if validate_type and value is not None:
            if not isinstance(value, validate_type):
                logging.warning(f"Session data type mismatch for {key}: expected {validate_type}, got {type(value)}")
                return default
        
        return value
        
    except Exception as e:
        logging.error(f"Error accessing session key {key}: {e}")
        return default

def cleanup_session_data():
    """Clean up session data to prevent size issues."""
    try:
        # Remove temporary data
        temp_keys = ["new_content", "temp_story", "error_state", "debug_info"]
        for key in temp_keys:
            session.pop(key, None)
        
        # Compress story history if too large
        story_history = session.get("story_history", [])
        if len(story_history) > 8:
            # Keep only recent entries
            session["story_history"] = story_history[-6:]
            logging.info("Compressed story history to manage session size")
        
        # Check session size and log warning
        import sys
        session_size = sys.getsizeof(str(dict(session)))
        if session_size > 3000:  # Approaching Flask session limit
            logging.warning(f"Session size is large: {session_size} bytes")
            
    except Exception as e:
        logging.error(f"Error during session cleanup: {e}")

def create_error_response(error_type: str, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create standardized error response."""
    response = {
        "success": False,
        "error_type": error_type,
        "message": message,
        "timestamp": __import__("datetime").datetime.now().isoformat()
    }
    
    if details:
        response["details"] = details
    
    return response

class GameStateValidator:
    """Validates and fixes game state inconsistencies."""
    
    @staticmethod
    def validate_player_health(player: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure player health is within valid bounds."""
        max_health = player.get("max_health", 100)
        current_health = player.get("health", max_health)
        
        # Fix invalid values
        player["max_health"] = max(1, max_health)
        player["health"] = max(0, min(player["max_health"], current_health))
        
        return player
    
    @staticmethod
    def validate_resources(resources: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure resources are within valid bounds."""
        resource_limits = {
            "ammo": (0, 999),
            "medkits": (0, 20), 
            "grenades": (0, 10),
            "food": (0, 15)
        }
        
        for resource, (min_val, max_val) in resource_limits.items():
            current = resources.get(resource, 0)
            resources[resource] = max(min_val, min(max_val, current))
        
        return resources
    
    @staticmethod
    def validate_mission_state(mission: Dict[str, Any]) -> Dict[str, Any]:
        """Validate mission data."""
        required_fields = {
            "name": "Unknown Mission",
            "difficulty": "Medium",
            "location": "Unknown Location",
            "desc": "Complete your assigned objectives."
        }
        
        for field, default in required_fields.items():
            if not mission.get(field):
                mission[field] = default
        
        # Validate difficulty
        if mission.get("difficulty") not in ["Easy", "Medium", "Hard"]:
            mission["difficulty"] = "Medium"
        
        return mission

def recovery_mode_handler(error: Exception) -> str:
    """Handle critical errors by entering recovery mode."""
    logging.critical(f"Entering recovery mode due to: {error}")
    
    # Clear problematic session data
    session.clear()
    
    # Set recovery state
    session["recovery_mode"] = True
    session["recovery_reason"] = str(error)
    
    return redirect(url_for("index"))