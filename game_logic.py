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

def generate_combat_scenario(player: Dict[str, Any], mission: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a detailed combat scenario with enemies and environment."""
    difficulty = mission.get("difficulty", "medium").lower()
    mission_type = mission.get("name", "").lower()
    
    # Environment based on mission type
    environments = {
        "village": "urban",
        "bridge": "open_field", 
        "bunker": "bunker",
        "forest": "forest",
        "beach": "open_field"
    }
    
    environment = "forest"  # default
    for key, env in environments.items():
        if key in mission_type:
            environment = env
            break
    
    # Enemy types and counts based on difficulty
    enemy_configs = {
        "easy": {
            "count": random.randint(2, 3),
            "types": ["soldier", "soldier", "rifleman"]
        },
        "medium": {
            "count": random.randint(3, 4), 
            "types": ["soldier", "soldier", "gunner", "officer"]
        },
        "hard": {
            "count": random.randint(4, 6),
            "types": ["soldier", "gunner", "officer", "sniper", "heavy"]
        }
    }
    
    config = enemy_configs.get(difficulty, enemy_configs["medium"])
    enemy_count = config["count"]
    
    # Generate enemies
    enemies = []
    enemy_types = config["types"]
    
    for i in range(enemy_count):
        enemy_type = random.choice(enemy_types)
        enemy = create_enemy(enemy_type, environment)
        enemy["id"] = f"enemy_{i+1}"
        enemies.append(enemy)
    
    return {
        "environment": environment,
        "enemies": enemies,
        "player_advantages": get_player_advantages(player, environment),
        "environmental_effects": get_environmental_effects(environment)
    }

def create_enemy(enemy_type: str, environment: str) -> Dict[str, Any]:
    """Create an enemy with type-specific stats."""
    base_enemies = {
        "soldier": {
            "type": "German Soldier",
            "health": random.randint(60, 80),
            "accuracy": 0.65,
            "damage": random.randint(15, 25),
            "armor": 0,
            "special": None
        },
        "rifleman": {
            "type": "German Rifleman", 
            "health": random.randint(70, 90),
            "accuracy": 0.75,
            "damage": random.randint(20, 30),
            "armor": 0,
            "special": "aimed_shot"
        },
        "gunner": {
            "type": "Machine Gunner",
            "health": random.randint(80, 100),
            "accuracy": 0.60,
            "damage": random.randint(25, 35),
            "armor": 5,
            "special": "suppressive_fire"
        },
        "sniper": {
            "type": "German Sniper",
            "health": random.randint(50, 70),
            "accuracy": 0.90,
            "damage": random.randint(35, 50),
            "armor": 0,
            "special": "precision_shot"
        },
        "officer": {
            "type": "German Officer",
            "health": random.randint(70, 90),
            "accuracy": 0.70,
            "damage": random.randint(20, 30),
            "armor": 5,
            "special": "rally_troops"
        },
        "heavy": {
            "type": "Heavy Gunner",
            "health": random.randint(100, 120),
            "accuracy": 0.55,
            "damage": random.randint(30, 45),
            "armor": 10,
            "special": "heavy_suppression"
        }
    }
    
    enemy = base_enemies.get(enemy_type, base_enemies["soldier"]).copy()
    enemy["maxHealth"] = enemy["health"]  # Store max health for health bars
    enemy["max_health"] = enemy["health"]  # Backup property name
    enemy["inCover"] = random.choice([True, False])
    enemy["suppressed"] = False
    enemy["position"] = get_enemy_position(environment)
    
    return enemy

def get_enemy_position(environment: str) -> str:
    """Get tactical position description based on environment."""
    positions = {
        "urban": ["behind rubble", "in a doorway", "around a corner", "on a rooftop"],
        "forest": ["behind trees", "in thick brush", "on elevated ground", "in a clearing"],
        "bunker": ["behind concrete", "in a fortified position", "near gun ports", "in trenches"],
        "open_field": ["in a crater", "behind low cover", "in tall grass", "on a small hill"]
    }
    return random.choice(positions.get(environment, positions["open_field"]))

def get_player_advantages(player: Dict[str, Any], environment: str) -> List[str]:
    """Get player advantages based on class and environment."""
    advantages = []
    player_class = player.get("class", "rifleman").lower()
    
    class_advantages = {
        "sniper": {
            "forest": "Camouflage training gives stealth bonus",
            "open_field": "Long range training provides accuracy bonus"
        },
        "demolitions": {
            "bunker": "Explosive expertise effective against fortifications",
            "urban": "Urban warfare training provides tactical advantage"
        },
        "medic": {
            "any": "Medical training allows squad healing during combat"
        },
        "gunner": {
            "open_field": "Machine gun training effective in open terrain",
            "bunker": "Suppressive fire training effective in confined spaces"
        }
    }
    
    if player_class in class_advantages:
        class_advs = class_advantages[player_class]
        if environment in class_advs:
            advantages.append(class_advs[environment])
        elif "any" in class_advs:
            advantages.append(class_advs["any"])
    
    return advantages

def get_environmental_effects(environment: str) -> Dict[str, str]:
    """Get environmental effects that impact combat."""
    effects = {
        "urban": {
            "cover": "Abundant hard cover available",
            "movement": "Close quarters limit long-range engagements",
            "special": "Grenades more effective due to confined spaces"
        },
        "forest": {
            "cover": "Natural camouflage and tree cover", 
            "movement": "Dense vegetation limits visibility",
            "special": "Flanking maneuvers easier to execute"
        },
        "bunker": {
            "cover": "Heavy fortified positions",
            "movement": "Restricted movement in tunnels",
            "special": "Explosives highly effective against structures"
        },
        "open_field": {
            "cover": "Limited natural cover available",
            "movement": "Clear fields of fire for all units",
            "special": "Long-range weapons have maximum effectiveness"
        }
    }
    return effects.get(environment, effects["open_field"])

def generate_squad_members(player: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate squad members based on mission and player rank."""
    rank = player.get("rank", "private").lower()
    
    # Squad size based on rank
    squad_sizes = {
        "private": 2,
        "corporal": 3, 
        "sergeant": 4,
        "lieutenant": 5,
        "captain": 6
    }
    
    squad_size = squad_sizes.get(rank, 2)
    
    # Possible squad member types
    member_types = [
        {"name": "Rifleman", "speciality": "assault", "weapon": "M1 Garand"},
        {"name": "Gunner", "speciality": "support", "weapon": "BAR"},
        {"name": "Medic", "speciality": "medical", "weapon": "Carbine"},
        {"name": "Demolitions", "speciality": "explosives", "weapon": "SMG"},
        {"name": "Radioman", "speciality": "communications", "weapon": "Carbine"},
        {"name": "Scout", "speciality": "reconnaissance", "weapon": "SMG"}
    ]
    
    squad = []
    for i in range(squad_size):
        member_type = random.choice(member_types)
        member = {
            "id": f"squad_{i+1}",
            "name": f"Pvt. {chr(65+i)}", # A, B, C, etc.
            "speciality": member_type["speciality"],
            "weapon": member_type["weapon"],
            "health": random.randint(80, 100),
            "max_health": 100,
            "ammo": random.randint(20, 30),
            "inCover": False,
            "suppressed": False,
            "orders": "follow",  # follow, attack, defend, flank
            "experience": random.randint(1, 3)  # affects performance
        }
        squad.append(member)
    
    return squad

def resolve_combat_encounter(player: Dict[str, Any], chosen_action: str, mission: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a simple combat encounter - legacy function for compatibility."""
    # This is now a simplified version for backward compatibility
    # The main combat system uses the new generate_combat_scenario function
    
    player_class = player.get("class", "rifleman").lower()
    player_weapon = player.get("weapon", "rifle").lower()
    player_health = player.get("health", 100)
    
    # Generate a quick combat scenario
    scenario = generate_combat_scenario(player, mission)
    
    # Simple resolution for story integration
    victory_chance = 70  # Base chance
    
    # Apply modifiers
    if player_health < 50:
        victory_chance -= 20
    if player_class == "sniper":
        victory_chance += 10
    if "careful" in chosen_action.lower():
        victory_chance += 15
    
    victory = random.randint(1, 100) <= victory_chance
    
    if victory:
        damage_taken = random.randint(0, 15)
        ammo_used = random.randint(1, 3)
        description = f"Victory! Your tactical approach proved effective against {len(scenario['enemies'])} enemies."
    else:
        damage_taken = random.randint(10, 25)
        ammo_used = random.randint(2, 5)
        description = f"The engagement was difficult. Enemy forces inflicted casualties."
    
    return {
        "victory": victory,
        "damage": damage_taken,
        "ammo_used": ammo_used,
        "description": description,
        "scenario": scenario
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