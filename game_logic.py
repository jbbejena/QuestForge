"""
Game Logic Module - Core gameplay functions extracted from app.py
Handles mission generation, combat, choices, and game state management
"""

import random
import logging
import re
from typing import Dict, List, Any, Optional
from flask import session

def get_session_id() -> str:
    """Generate or retrieve session ID for database operations."""
    if "session_id" not in session:
        import uuid
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]

def resolve_combat_encounter(player: Dict[str, Any], chosen_action: str, mission: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a combat encounter with tactical outcomes."""
    player_class = player.get("class", "rifleman").lower()
    player_weapon = player.get("weapon", "rifle").lower()
    player_health = player.get("health", 100)
    
    # Base combat effectiveness
    combat_effectiveness = 50
    
    # Class bonuses
    class_bonuses = {
        "rifleman": {"accuracy": 10, "damage": 5},
        "sniper": {"accuracy": 20, "damage": 15, "stealth": 10},
        "gunner": {"suppression": 15, "damage": 10},
        "medic": {"survival": 20, "healing": 15},
        "demolitions": {"explosive": 25, "breach": 15}
    }
    
    if player_class in class_bonuses:
        bonuses = class_bonuses[player_class]
        combat_effectiveness += sum(bonuses.values()) // 2
    
    # Weapon effectiveness
    weapon_bonuses = {
        "rifle": 10,
        "smg": 15,
        "lmg": 20,
        "sniper rifle": 25,
        "shotgun": 12
    }
    combat_effectiveness += weapon_bonuses.get(player_weapon, 5)
    
    # Health affects performance
    health_multiplier = player_health / 100
    combat_effectiveness *= health_multiplier
    
    # Action analysis
    action_lower = chosen_action.lower()
    if any(word in action_lower for word in ["careful", "cautious", "plan"]):
        combat_effectiveness += 15
    elif any(word in action_lower for word in ["aggressive", "charge", "attack"]):
        combat_effectiveness += 10
    elif any(word in action_lower for word in ["retreat", "fall back", "withdraw"]):
        combat_effectiveness -= 20
    
    # Mission difficulty modifier
    difficulty = mission.get("difficulty", "medium").lower()
    difficulty_modifiers = {"easy": 20, "medium": 0, "hard": -15}
    combat_effectiveness += difficulty_modifiers.get(difficulty, 0)
    
    # Determine outcome
    victory_chance = max(10, min(90, combat_effectiveness))
    victory = random.randint(1, 100) <= victory_chance
    
    if victory:
        damage_taken = random.randint(0, 15)
        ammo_used = random.randint(1, 3)
        description = f"Victory! Your {player_class} training and {player_weapon} proved effective."
    else:
        damage_taken = random.randint(10, 30)
        ammo_used = random.randint(2, 5)
        description = f"The engagement was costly. You took significant casualties."
    
    return {
        "victory": victory,
        "damage": damage_taken,
        "ammo_used": ammo_used,
        "description": description,
        "effectiveness": combat_effectiveness
    }

def detect_mission_outcome(story_content: str) -> Optional[str]:
    """Enhanced mission outcome detection with better keyword analysis."""
    if not story_content:
        return None
    
    story_lower = story_content.lower()
    
    # Success indicators with weights
    success_indicators = [
        ("mission accomplished", 10),
        ("objective complete", 10),
        ("mission successful", 10),
        ("victory", 8),
        ("objective secured", 9),
        ("target destroyed", 9),
        ("successfully completed", 8),
        ("mission complete", 10),
        ("beach secured", 8),
        ("objective achieved", 9)
    ]
    
    # Failure indicators with weights  
    failure_indicators = [
        ("mission failed", 10),
        ("retreat", 7),
        ("objective lost", 9),
        ("defeated", 8),
        ("overwhelmed", 8),
        ("forced to withdraw", 9),
        ("mission aborted", 10),
        ("casualty rate too high", 9),
        ("squad eliminated", 10),
        ("captured", 8)
    ]
    
    success_score = sum(weight for keyword, weight in success_indicators if keyword in story_lower)
    failure_score = sum(weight for keyword, weight in failure_indicators if keyword in story_lower)
    
    # Clear determination
    if success_score > failure_score + 5:
        return "success"
    elif failure_score > success_score + 5:
        return "failure"
    
    # Check turn count for long missions
    turn_count = session.get("turn_count", 0)
    if turn_count >= 7:
        # Look for resolution indicators in final turns
        if any(word in story_lower for word in ["secured", "completed", "achieved", "accomplished"]):
            return "success"
        elif any(word in story_lower for word in ["failed", "lost", "retreat", "withdrawn"]):
            return "failure"
    
    return None

def extract_choices_from_story(story_content: str) -> Dict[int, str]:
    """Enhanced choice extraction with better parsing."""
    choices = {}
    
    if not story_content:
        return choices
    
    # Multiple choice patterns
    patterns = [
        r'\n(\d+)\.\s*(.+?)(?=\n\d+\.|$)',  # Numbered choices
        r'\n([A-C])\)\s*(.+?)(?=\n[A-C]\)|$)',  # Lettered choices
        r'Choice (\d+):\s*(.+?)(?=Choice \d+:|$)',  # "Choice X:" format
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, story_content, re.MULTILINE | re.DOTALL)
        if matches:
            for i, (choice_num, choice_text) in enumerate(matches, 1):
                choice_text = choice_text.strip()
                choice_text = re.sub(r'\n+', ' ', choice_text)  # Replace newlines
                choice_text = choice_text.rstrip('.')  # Remove trailing period
                
                if len(choice_text) > 5:  # Only accept substantial choices
                    try:
                        num = int(choice_num) if choice_num.isdigit() else i
                        choices[num] = choice_text
                    except:
                        choices[i] = choice_text
            break
    
    return choices

def validate_game_state(player: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize game state to prevent issues."""
    # Ensure player has required fields
    player.setdefault("name", "Unknown Soldier")
    player.setdefault("rank", "Private")
    player.setdefault("class", "Rifleman")
    player.setdefault("weapon", "Rifle")
    player.setdefault("health", 100)
    player.setdefault("max_health", 100)
    player.setdefault("morale", 100)
    
    # Validate health bounds
    player["health"] = max(0, min(player["max_health"], player.get("health", 100)))
    player["morale"] = max(0, min(100, player.get("morale", 100)))
    
    # Ensure resources have required fields
    resources.setdefault("ammo", 30)
    resources.setdefault("medkits", 2)
    resources.setdefault("grenades", 1)
    resources.setdefault("food", 3)
    
    # Validate resource bounds
    for resource in ["ammo", "medkits", "grenades", "food"]:
        resources[resource] = max(0, resources.get(resource, 0))
    
    return {"player": player, "resources": resources}

def calculate_mission_score(mission: Dict[str, Any], outcome: str, turn_count: int, 
                          combat_victories: int = 0) -> int:
    """Calculate mission score based on performance."""
    base_scores = {"easy": 50, "medium": 100, "hard": 150}
    difficulty = mission.get("difficulty", "medium").lower()
    base_score = base_scores.get(difficulty, 100)
    
    # Outcome multiplier
    outcome_multipliers = {"success": 1.0, "failure": 0.3}
    score = int(base_score * outcome_multipliers.get(outcome, 0.5))
    
    # Efficiency bonus (fewer turns = better)
    if turn_count <= 5 and outcome == "success":
        score += 50  # Speed bonus
    elif turn_count >= 10:
        score = int(score * 0.8)  # Efficiency penalty
    
    # Combat bonus
    score += combat_victories * 20
    
    return max(0, score)

def get_fallback_story(turn_count: int = 0) -> str:
    """Provide engaging fallback content when AI is unavailable."""
    if turn_count == 0:
        stories = [
            "The morning mist hangs heavy over the battlefield as you advance with your squad. Intelligence reports enemy movement ahead.\n\n1. Move forward cautiously through the trees.\n2. Send a scout to investigate the area.\n3. Set up defensive positions and wait.",
            "Your radio crackles with urgent messages from command. The situation is developing rapidly.\n\n1. Request immediate reinforcements.\n2. Advance to the objective as planned.\n3. Fall back to a safer position."
        ]
    elif turn_count < 3:
        stories = [
            "As you advance, the tension increases. Your squad spots movement in the distance.\n\n1. Order the squad to take cover.\n2. Advance closer to investigate.\n3. Use binoculars to assess the threat.",
            "Enemy patrol spotted ahead! Your heart pounds as you make a critical decision.\n\n1. Engage the enemy immediately.\n2. Wait for them to pass.\n3. Circle around to avoid contact."
        ]
    else:
        stories = [
            "The objective is within reach. This is your chance to complete the mission.\n\n1. Make a final push to the objective.\n2. Secure the area first.\n3. Call for backup before proceeding.",
            "Enemy reinforcements are approaching your position. Time is running out.\n\n1. Complete the mission quickly.\n2. Prepare for a fighting withdrawal.\n3. Request immediate extraction."
        ]
    
    return random.choice(stories)

# Combat keywords for story analysis
COMBAT_KEYWORDS = [
    "combat", "ambush", "ambushed", "attack begins", "sudden attack", "under fire",
    "opens fire", "open fire", "firefight", "enemy fires", "battle erupts",
    "exchange of gunfire", "hostilities commence", "start shooting", "start firing",
    "enemy spotted", "take cover", "incoming fire", "gunshots ring out"
]

# Mission outcome keywords
SUCCESS_KEYWORDS = [
    "mission accomplished", "objective complete", "mission successful", "victory",
    "objective secured", "target destroyed", "successfully completed", "mission complete",
    "beach secured", "objective achieved", "successfully infiltrated", "enemy eliminated"
]

FAILURE_KEYWORDS = [
    "mission failed", "retreat", "objective lost", "defeated", "overwhelmed",
    "forced to withdraw", "mission aborted", "casualty rate too high", "squad eliminated",
    "captured", "surrounded", "no survivors"
]