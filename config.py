"""
Game Configuration Module
Centralized configuration and constants for WWII Text Adventure
"""

import os
from typing import Dict, Any, List, Optional

# Game Data Configuration
RANKS: List[str] = ["Private", "Corporal", "Sergeant", "Lieutenant", "Captain"]
CLASSES: List[str] = ["Rifleman", "Medic", "Gunner", "Sniper", "Demolitions"] 
WEAPONS: List[str] = ["Rifle", "SMG", "LMG", "Sniper Rifle", "Shotgun"]

# Campaign Configuration - starts with D-Day
INITIAL_MISSION: Dict[str, Any] = {
    "name": "Operation Overlord - D-Day",
    "desc": "Storm the beaches of Normandy with your squad. The fate of Europe hangs in the balance.",
    "difficulty": "Hard",
    "location": "Omaha Beach, Normandy", 
    "date": "June 6, 1944",
    "is_campaign_start": True
}

# Mission Difficulty Settings
DIFFICULTY_SETTINGS: Dict[str, Dict[str, Any]] = {
    "Easy": {
        "enemy_count_multiplier": 0.8,
        "damage_reduction": 0.7,
        "reward_multiplier": 0.9,
        "ai_complexity": "low"
    },
    "Medium": {
        "enemy_count_multiplier": 1.0,
        "damage_reduction": 1.0,
        "reward_multiplier": 1.0,
        "ai_complexity": "medium"
    },
    "Hard": {
        "enemy_count_multiplier": 1.3,
        "damage_reduction": 1.2,
        "reward_multiplier": 1.2,
        "ai_complexity": "high"
    }
}

# Session Management Configuration
SESSION_CONFIG: Dict[str, Any] = {
    "max_story_history": 8,
    "max_session_size_bytes": 3000,
    "auto_cleanup_interval": 5,  # turns
    "story_summary_threshold": 800,  # characters
    "permanent_session_lifetime": 86400  # 24 hours
}

# AI Configuration
AI_CONFIG: Dict[str, Any] = {
    "story_generation": {
        "max_tokens": 350,
        "temperature": 0.8,
        "top_p": 0.9
    },
    "story_summary": {
        "max_tokens": 200,
        "temperature": 0.3,
        "top_p": 0.8
    },
    "combat_generation": {
        "max_tokens": 250,
        "temperature": 0.7,
        "top_p": 0.85
    }
}

# Performance Settings
PERFORMANCE_CONFIG: Dict[str, Any] = {
    "enable_caching": True,
    "cache_ttl_seconds": 300,  # 5 minutes
    "batch_session_updates": True,
    "monitor_performance": True
}

# Logging Configuration
LOGGING_CONFIG: Dict[str, Any] = {
    "level": "DEBUG",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_ai_requests": True,
    "log_session_operations": True,
    "log_database_operations": True
}

# Flask Application Settings
FLASK_CONFIG: Dict[str, Any] = {
    "secret_key_env": "SESSION_SECRET",
    "default_secret_key": "dev-secret-key-change-in-production",
    "session_permanent": True,
    "host": "0.0.0.0",
    "port": 5000,
    "debug": True
}

def get_env_config() -> Dict[str, Optional[str]]:
    """Get environment-specific configuration."""
    return {
        "openai_api_key": os.environ.get("OPENAI_API_KEY"),
        "database_url": os.environ.get("DATABASE_URL"),
        "session_secret": os.environ.get("SESSION_SECRET", FLASK_CONFIG["default_secret_key"]),
        "environment": os.environ.get("ENVIRONMENT", "development")
    }

def get_ai_prompt_templates() -> Dict[str, str]:
    """Get AI prompt templates for different game scenarios."""
    return {
        "story_generation": """
You are a WWII military storyteller. Continue this mission story with historically accurate details.
Mission: {mission_name}
Location: {location}
Date: {date}
Player: {player_name} ({rank}, {player_class})
Current situation: {current_story}
Choice made: {choice}

Generate 2-3 paragraphs continuing the story with realistic combat, tactics, and WWII atmosphere. 
End with 2-3 tactical choices for the player.
""",
        
        "combat_resolution": """
Resolve this WWII combat encounter:
Player: {player_name} ({player_class}, {weapon})
Enemies: {enemies}
Environment: {environment}
Action taken: {action}

Describe the combat outcome in 1-2 paragraphs with realistic military tactics and consequences.
""",
        
        "mission_briefing": """
Generate a WWII mission briefing:
Mission Type: {mission_type}
Location: {location}
Difficulty: {difficulty}
Historical Context: {historical_context}

Create a 2-paragraph briefing with objectives, enemy intelligence, and tactical considerations.
"""
    }