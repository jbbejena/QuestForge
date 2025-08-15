"""
Achievement System with Historical War Trivia
Tracks player progress and unlocks historical trivia facts
"""

import random
from typing import Dict, List, Any

# Historical War Trivia Database
HISTORICAL_TRIVIA = {
    "first_mission": {
        "title": "Operation Overlord",
        "fact": "D-Day involved over 156,000 Allied troops landing on the beaches of Normandy on June 6, 1944. It was the largest seaborne invasion in history.",
        "category": "Major Operations"
    },
    "survivor": {
        "title": "Winter War Resilience", 
        "fact": "During the Winter War (1939-1940), Finnish soldiers used molotov cocktails effectively against Soviet tanks. They named them after Soviet Foreign Minister Vyacheslav Molotov.",
        "category": "Tactics & Weapons"
    },
    "combat_veteran": {
        "title": "Stalingrad Sniper",
        "fact": "Vasily Zaitsev, a Soviet sniper at Stalingrad, is credited with 225 confirmed kills. His story inspired the film 'Enemy at the Gates'.",
        "category": "Heroes & Legends"
    },
    "mission_master": {
        "title": "The Enigma Code",
        "fact": "Breaking the German Enigma code at Bletchley Park is estimated to have shortened WWII by 2-4 years and saved millions of lives.",
        "category": "Intelligence & Espionage"
    },
    "perfect_health": {
        "title": "Field Medicine",
        "fact": "WWII saw major advances in field medicine. The use of penicillin and blood plasma saved countless soldiers' lives on the battlefield.",
        "category": "Medical Advances"
    },
    "resource_manager": {
        "title": "Lend-Lease Program",
        "fact": "The U.S. Lend-Lease program provided over $50 billion worth of supplies to Allied nations, including 400,000 vehicles and 14,000 aircraft.",
        "category": "Supply & Logistics"
    },
    "squad_leader": {
        "title": "Band of Brothers",
        "fact": "Easy Company, 506th PIR, 101st Airborne Division fought from D-Day to Hitler's Eagle's Nest. Their story was immortalized by Stephen Ambrose and HBO.",
        "category": "Military Units"
    },
    "rapid_completion": {
        "title": "Operation Market Garden",
        "fact": "This ambitious Allied operation in September 1944 aimed to end the war by Christmas. Despite initial success, it ultimately failed at Arnhem.",
        "category": "Major Operations"
    },
    "high_scorer": {
        "title": "The Red Baron's Legacy",
        "fact": "While WWI, Manfred von Richthofen's tactics influenced WWII aerial combat. The highest-scoring WWII ace was Erich Hartmann with 352 victories.",
        "category": "Aviation"
    },
    "class_master": {
        "title": "Special Forces Origins",
        "fact": "WWII saw the birth of modern special forces, including the British SAS, U.S. Rangers, and Soviet Spetsnaz, revolutionizing military tactics.",
        "category": "Special Operations"
    }
}

# Achievement Definitions
ACHIEVEMENTS = {
    "first_mission": {
        "name": "First Deployment",
        "description": "Complete your first mission",
        "icon": "🎖️",
        "condition": "missions_completed >= 1"
    },
    "survivor": {
        "name": "Battle Survivor", 
        "description": "Survive 5 missions without dying",
        "icon": "⚡",
        "condition": "missions_completed >= 5 and deaths == 0"
    },
    "combat_veteran": {
        "name": "Combat Veteran",
        "description": "Win 10 combat encounters", 
        "icon": "💀",
        "condition": "combat_victories >= 10"
    },
    "mission_master": {
        "name": "Mission Master",
        "description": "Complete 15 missions successfully",
        "icon": "🏆",
        "condition": "missions_completed >= 15"
    },
    "perfect_health": {
        "name": "Field Medic",
        "description": "Complete a mission without taking damage",
        "icon": "🏥",
        "condition": "perfect_mission == True"
    },
    "resource_manager": {
        "name": "Supply Sergeant",
        "description": "Use 25 items during missions",
        "icon": "📦",
        "condition": "items_used >= 25"
    },
    "squad_leader": {
        "name": "Squad Leader",
        "description": "Lead your squad through 3 successful missions",
        "icon": "👥",
        "condition": "successful_squad_missions >= 3"
    },
    "rapid_completion": {
        "name": "Lightning Strike",
        "description": "Complete a mission in under 10 choices",
        "icon": "⚡",
        "condition": "quick_completion == True"
    },
    "high_scorer": {
        "name": "War Hero",
        "description": "Achieve a score of 1000 points",
        "icon": "🌟",
        "condition": "total_score >= 1000"
    },
    "class_master": {
        "name": "Master of War",
        "description": "Play as all 4 character classes",
        "icon": "🎭",
        "condition": "classes_played >= 4"
    }
}

def check_achievements(player_stats: Dict[str, Any]) -> List[str]:
    """Check which achievements have been unlocked based on player stats."""
    unlocked = []
    
    for achievement_id, achievement in ACHIEVEMENTS.items():
        condition = achievement["condition"]
        
        # Skip if already unlocked
        if achievement_id in player_stats.get("achievements_unlocked", []):
            continue
            
        # Evaluate condition
        try:
            # Create a safe evaluation context with player stats
            eval_context = {
                'missions_completed': player_stats.get('missions_completed', 0),
                'deaths': player_stats.get('deaths', 0),
                'combat_victories': player_stats.get('combat_victories', 0),
                'perfect_mission': player_stats.get('perfect_mission', False),
                'items_used': player_stats.get('items_used', 0),
                'successful_squad_missions': player_stats.get('successful_squad_missions', 0),
                'quick_completion': player_stats.get('quick_completion', False),
                'total_score': player_stats.get('total_score', 0),
                'classes_played': len(set(player_stats.get('classes_used', [])))
            }
            
            if eval(condition, {"__builtins__": {}}, eval_context):
                unlocked.append(achievement_id)
                
        except Exception as e:
            print(f"Error evaluating achievement {achievement_id}: {e}")
            continue
    
    return unlocked

def get_achievement_display(achievement_id: str) -> Dict[str, str]:
    """Get display information for an achievement."""
    achievement = ACHIEVEMENTS.get(achievement_id, {})
    trivia = HISTORICAL_TRIVIA.get(achievement_id, {})
    
    return {
        "id": achievement_id,
        "name": achievement.get("name", "Unknown Achievement"),
        "description": achievement.get("description", ""),
        "icon": achievement.get("icon", "🎖️"),
        "trivia_title": trivia.get("title", "Historical Fact"),
        "trivia_fact": trivia.get("fact", "An interesting piece of WWII history."),
        "trivia_category": trivia.get("category", "General")
    }

def initialize_player_stats() -> Dict[str, Any]:
    """Initialize player statistics for achievement tracking."""
    return {
        "missions_completed": 0,
        "deaths": 0,
        "combat_victories": 0,
        "items_used": 0,
        "successful_squad_missions": 0,
        "total_score": 0,
        "classes_used": [],
        "achievements_unlocked": [],
        "perfect_mission": False,
        "quick_completion": False,
        "current_mission_choices": 0,
        "current_mission_damage_taken": 0
    }

def update_player_stats(stats: Dict[str, Any], event: str, **kwargs) -> Dict[str, Any]:
    """Update player statistics based on game events."""
    if event == "mission_completed":
        stats["missions_completed"] += 1
        stats["total_score"] += kwargs.get("score", 0)
        
        # Check for perfect mission (no damage taken)
        if stats.get("current_mission_damage_taken", 0) == 0:
            stats["perfect_mission"] = True
            
        # Check for quick completion (under 10 choices)
        if stats.get("current_mission_choices", 0) < 10:
            stats["quick_completion"] = True
            
        # Reset mission-specific counters
        stats["current_mission_choices"] = 0
        stats["current_mission_damage_taken"] = 0
        
    elif event == "player_death":
        stats["deaths"] += 1
        
    elif event == "combat_victory":
        stats["combat_victories"] += 1
        
    elif event == "item_used":
        stats["items_used"] += 1
        
    elif event == "squad_mission_success":
        stats["successful_squad_missions"] += 1
        
    elif event == "class_selected":
        class_name = kwargs.get("class_name")
        if class_name and class_name not in stats.get("classes_used", []):
            if "classes_used" not in stats:
                stats["classes_used"] = []
            stats["classes_used"].append(class_name)
            
    elif event == "choice_made":
        stats["current_mission_choices"] += 1
        
    elif event == "damage_taken":
        damage = kwargs.get("damage", 0)
        stats["current_mission_damage_taken"] += damage
        
    return stats
