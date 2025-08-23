import os
import random
import re
import logging
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv

# Import new modular components
from config import (
    RANKS, CLASSES, WEAPONS, INITIAL_MISSION, DIFFICULTY_SETTINGS,
    SESSION_CONFIG, AI_CONFIG, get_env_config, get_ai_prompt_templates
)
from session_manager import session_manager
from story_manager import story_manager
from database import db, is_replit_database_available
from replit_session_manager import (
    replit_session, set_player_data, get_player_data,
    set_game_state, get_game_state, set_story_data, get_story_data
)
from achievements import (
    check_achievements, get_achievement_display, initialize_player_stats, 
    update_player_stats, ACHIEVEMENTS
)
from game_logic import (
    get_session_id, resolve_combat_encounter, detect_mission_outcome,
    extract_choices_from_story, validate_game_state, calculate_mission_score,
    get_fallback_story, COMBAT_KEYWORDS, SUCCESS_KEYWORDS, FAILURE_KEYWORDS
)
from mission_generator import generate_next_mission, get_mission_briefing_context
from error_handlers import (
    handle_session_error, handle_database_error, handle_ai_error,
    validate_player_session, safe_session_get, cleanup_session_data,
    GameStateValidator
)
from performance_utils import (
    perf_monitor, SessionCache, optimize_session_size, 
    batch_session_updates, cache_ai_response, get_cached_ai_response
)

# Configure enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    logging.warning("OpenAI package not installed. AI features will be disabled.")

# Load environment variables
load_dotenv()

# Get configuration from config module
env_config = get_env_config()
OPENAI_API_KEY = env_config["openai_api_key"]

# Initialize Flask app with configuration
app = Flask(__name__)
app.secret_key = env_config["session_secret"]
app.permanent_session_lifetime = SESSION_CONFIG["permanent_session_lifetime"]
app.config['SESSION_PERMANENT'] = True

# Initialize OpenAI client and connect to story manager
client = None
if OPENAI_API_KEY and OpenAI is not None:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        story_manager.client = client  # Connect AI client to story manager
        logging.info("OpenAI client initialized and connected to story manager")
    except Exception as e:
        logging.error(f"OpenAI initialization error: {e}")
else:
    logging.warning("OpenAI API key not found or OpenAI not installed")

# Campaign starts with D-Day
INITIAL_MISSION = {
    "name": "Operation Overlord - D-Day",
    "desc": "Storm the beaches of Normandy with your squad. The fate of Europe hangs in the balance.",
    "difficulty": "Hard",
    "location": "Omaha Beach, Normandy", 
    "date": "June 6, 1944",
    "is_campaign_start": True
}

def create_story_summary_legacy(full_story: str, mission: dict, player: dict) -> str:
    """Create an intelligent summary that preserves key plot points."""
    # Use the new story manager for better story summarization
    return story_manager.create_story_summary(full_story, mission, player)
    
    # Extract key elements to preserve
    key_phrases = []
    story_lower = full_story.lower()
    
    # Mission-specific key elements
    mission_name = mission.get("name", "").lower()
    if "sabotage" in mission_name:
        key_phrases.extend(["bridge", "explosives", "charges", "demolition", "target"])
    elif "rescue" in mission_name:
        key_phrases.extend(["prisoners", "pows", "rescue", "extraction", "captives"])
    elif "intel" in mission_name:
        key_phrases.extend(["documents", "intelligence", "classified", "information", "files"])
    
    # Character and tactical elements
    key_phrases.extend([
        player.get("name", "").lower(),
        player.get("class", "").lower(),
        "squad", "enemy", "objective", "mission"
    ])
    
    # Use AI to create intelligent summary if available
    if client:
        summary_prompt = (
            f"Compress this WWII mission story to under 400 words while preserving key plot points, "
            f"character decisions, mission objectives, and current tactical situation. "
            f"Key elements to preserve: {', '.join(key_phrases)}. "
            f"Story: {full_story}"
        )
        
        try:
            ai_summary = ai_chat(
                "You are an expert story editor. Create concise but complete summaries.",
                summary_prompt,
                temperature=0.3,
                max_tokens=200
            )
            if len(ai_summary) < len(full_story) * 0.7:  # Only use if significantly shorter
                return ai_summary
        except Exception as e:
            logging.warning(f"AI summary failed: {e}")
    
    # Fallback to original sentence-scoring method
    sentences = full_story.split('. ')
    scored_sentences = []
    
    for sentence in sentences:
        score = 0
        sentence_lower = sentence.lower()
        
        # Score based on key phrases
        for phrase in key_phrases:
            if phrase and phrase in sentence_lower:
                score += 1
        
        # Boost sentences with tactical/action content
        if any(word in sentence_lower for word in ["attack", "advance", "enemy", "fire", "combat"]):
            score += 1
        
        # Boost recent choices (sentences containing "chose" or numbers)
        if "chose" in sentence_lower or any(str(i) in sentence for i in range(1, 4)):
            score += 2
        
        scored_sentences.append((score, sentence))
    
    # Keep highest scoring sentences plus ensure narrative flow
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    
    # Take top sentences but ensure we have intro and recent content
    summary_sentences = []
    
    # Always keep first 2 sentences (mission setup)
    if len(sentences) > 2:
        summary_sentences.extend(sentences[:2])
    
    # Add highest scoring middle content
    middle_sentences = [s[1] for s in scored_sentences if s[0] > 0][:3]
    summary_sentences.extend(middle_sentences)
    
    # Always keep last 3 sentences (current situation)
    if len(sentences) > 3:
        summary_sentences.extend(sentences[-3:])
    
    # Remove duplicates while preserving order
    seen = set()
    final_sentences = []
    for sentence in summary_sentences:
        if sentence not in seen:
            seen.add(sentence)
            final_sentences.append(sentence)
    
    summary = '. '.join(final_sentences)
    
    # Add bridging text to maintain flow
    if len(final_sentences) > 5:
        summary += "\n\n[Mission continues with tactical precision...]"
    
    return summary

# Mission generation function moved to mission_generator.py

# Mission outcome detection moved to game_logic.py

def ai_chat(system_msg: str, user_prompt: str, temperature: float = 0.8, max_tokens: int = 700) -> str:
    """
    Call OpenAI API to generate story content.
    Returns AI-generated text or fallback content if API is unavailable.
    """
    if client is None:
        # Enhanced fallback content with progression tracking
        turn_count = session.get("turn_count", 0)
        
        if turn_count == 0:
            fallback_stories = [
                "The morning mist hangs heavy over the battlefield as you advance with your squad. Intelligence reports enemy movement ahead.\n\n1. Move forward cautiously through the trees.\n2. Send a scout to investigate the area.\n3. Set up defensive positions and wait.",
                "Your radio crackles with urgent messages from command. The situation is developing rapidly.\n\n1. Request immediate reinforcements.\n2. Advance to the objective as planned.\n3. Fall back to a safer position."
            ]
        elif turn_count < 3:
            fallback_stories = [
                "As you advance, the tension increases. Your squad spots movement in the distance.\n\n1. Order the squad to take cover.\n2. Advance closer to investigate.\n3. Use binoculars to assess the threat.",
                "Enemy patrol spotted ahead! Your heart pounds as you make a critical decision.\n\n1. Engage the enemy immediately.\n2. Wait for them to pass.\n3. Circle around to avoid contact."
            ]
        else:
            fallback_stories = [
                "The objective is within reach. This is your chance to complete the mission.\n\n1. Make a final push to the objective.\n2. Secure the area first.\n3. Call for backup before proceeding."
            ]
        
        return random.choice(fallback_stories)
    
    try:
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        return "(Communication disrupted) Radio static fills the air. Your squad looks to you for guidance.\n\n1. Try to re-establish contact.\n2. Proceed with the mission as planned.\n3. Return to base for new orders."

def parse_choices(text: str):
    """Extract numbered choices from AI-generated text with improved parsing."""
    if not text:
        return ["Continue forward.", "Take defensive position.", "Retreat to safety."]
    
    lines = text.splitlines()
    choices = {}  # Use dict to handle out-of-order choices
    
    # Look through all lines for choice patterns
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Match patterns like "1. Choice text" or "1) Choice text" or "1 - Choice text"
        match = re.match(r"^\s*([1-3])[\.\)\-\:\s]+(.+)", line)
        if match:
            choice_number = int(match.group(1))
            choice_text = match.group(2).strip()
            
            # Clean up the choice text
            choice_text = re.sub(r'<[^>]+>', '', choice_text)  # Remove HTML
            choice_text = re.sub(r'\*\*([^\*]*)\*\*', r'\1', choice_text)  # Remove bold
            choice_text = re.sub(r'\*([^\*]*)\*', r'\1', choice_text)  # Remove italic
            choice_text = choice_text.rstrip('.')  # Remove trailing period if present
            
            if len(choice_text) > 5:  # Only accept substantial choices
                choices[choice_number] = choice_text
    
    # Convert to ordered list
    ordered_choices = []
    for i in range(1, 4):
        if i in choices:
            ordered_choices.append(choices[i])
    
    # If we don't have 3 choices, add fallback choices
    fallback_choices = [
        "Advance cautiously forward",
        "Take defensive position and observe", 
        "Retreat to a safer location"
    ]
    
    while len(ordered_choices) < 3:
        fallback_index = len(ordered_choices)
        if fallback_index < len(fallback_choices):
            ordered_choices.append(fallback_choices[fallback_index])
        else:
            ordered_choices.append("Continue with the mission")
    
    logging.info(f"Parsed choices from text: {ordered_choices}")
    return ordered_choices[:3]

def get_difficulty_modifier(difficulty: str) -> dict:
    """Get difficulty-based modifiers for missions."""
    modifiers = {
        "Easy": {"health_loss_min": 0, "health_loss_max": 10, "reward": 50, "event_chance": 0.3},
        "Medium": {"health_loss_min": 5, "health_loss_max": 20, "reward": 100, "event_chance": 0.4},
        "Hard": {"health_loss_min": 10, "health_loss_max": 30, "reward": 200, "event_chance": 0.5}
    }
    return modifiers.get(difficulty, modifiers["Medium"])

def generate_contextual_choices(player: dict, mission: dict, turn_count: int) -> list:
    """Generate contextual fallback choices based on current game state."""
    mission_type = mission.get("name", "").lower()
    player_class = player.get("class", "Rifleman").lower()
    difficulty = mission.get("difficulty", "Medium")
    
    # Base choice templates
    combat_choices = [
        "Engage the enemy with direct fire.",
        "Attempt to flank the enemy position.",
        "Call for covering fire and advance."
    ]
    
    stealth_choices = [
        "Move silently through the shadows.",
        "Create a distraction elsewhere.",
        "Wait for the patrol to pass."
    ]
    
    tactical_choices = [
        "Assess the tactical situation carefully.",
        "Coordinate with your squad members.",
        "Push forward to the objective."
    ]
    
    # Context-based choice selection
    if "sabotage" in mission_type or "demolitions" in player_class:
        return [
            "Set explosive charges on the target.",
            "Scout for alternative approaches.",
            "Signal the squad to provide cover."
        ]
    elif "rescue" in mission_type or "medic" in player_class:
        return [
            "Locate and assist wounded allies.",
            "Establish a safe extraction route.",
            "Provide medical support where needed."
        ]
    elif "sniper" in player_class:
        return [
            "Find an elevated firing position.",
            "Identify high-value targets.",
            "Provide overwatch for the team."
        ]
    elif turn_count > 3:
        return [
            "Make a final push to complete the mission.",
            "Secure the area before proceeding.",
            "Prepare for extraction."
        ]
    elif difficulty == "Hard":
        return combat_choices
    elif turn_count <= 2:
        return stealth_choices
    else:
        return tactical_choices

def generate_dynamic_consequences(chosen_action: str, player: dict, resources: dict, mission: dict, turn_count: int) -> str:
    """Generate dynamic consequences based on player choice and context."""
    events = []
    difficulty_mod = get_difficulty_modifier(mission.get("difficulty", "Medium"))
    player_class = player.get("class", "Rifleman")
    
    # Class-specific advantages
    class_bonuses = {
        "Medic": {"healing_boost": 1.5, "squad_protection": 0.8},
        "Sniper": {"stealth_bonus": 0.7, "precision_bonus": 1.2},
        "Gunner": {"suppression_bonus": 1.3, "ammo_efficiency": 0.9},
        "Demolitions": {"explosive_bonus": 1.5, "structural_damage": 1.4},
        "Rifleman": {"leadership_bonus": 1.1, "morale_boost": 1.2}
    }
    
    bonus = class_bonuses.get(player_class, class_bonuses["Rifleman"])
    
    # Analyze choice for consequence type
    action_lower = chosen_action.lower()
    
    # Combat consequences
    if any(word in action_lower for word in ["attack", "fire", "shoot", "engage", "assault"]):
        if random.random() < difficulty_mod["event_chance"]:
            if player_class == "Gunner" and random.random() < 0.3:
                events.append("Your machine gun suppresses the enemy effectively!")
                resources["ammo"] = max(0, resources.get("ammo", 0) - 2)
            else:
                damage = random.randint(difficulty_mod["health_loss_min"], difficulty_mod["health_loss_max"])
                if player_class == "Sniper":
                    damage = int(damage * 0.7)  # Snipers take less damage in combat
                player["health"] = max(0, player.get("health", 100) - damage)
                if damage > 0:
                    events.append(f"Combat is fierce! You take {damage} damage.")
                    
    # Stealth consequences  
    elif any(word in action_lower for word in ["sneak", "stealth", "quietly", "carefully", "scout"]):
        if player_class == "Sniper" and random.random() < 0.4:
            events.append("Your sniper training pays off - you move unseen.")
            resources["intel"] = resources.get("intel", 0) + 1
        elif random.random() < 0.3:
            events.append("You successfully avoid enemy detection.")
        else:
            events.append("You advance cautiously through enemy territory.")
            
    # Leadership/tactical consequences
    elif any(word in action_lower for word in ["order", "command", "lead", "coordinate", "direct"]):
        if player_class == "Rifleman" and random.random() < 0.3:
            events.append("Your leadership inspires the squad!")
            player["morale"] = min(100, player.get("morale", 100) + 10)
        elif random.random() < 0.2:
            events.append("The squad follows your tactical direction.")
            
    # Medical consequences
    elif any(word in action_lower for word in ["help", "treat", "medical", "wounded", "injured"]):
        if player_class == "Medic" and random.random() < 0.4:
            events.append("Your medical expertise saves valuable time and lives.")
    
    # Squad casualty system
    squad = session.get("squad", [])
    if squad and random.random() < 0.15:  # 15% chance of squad event
        if any(word in action_lower for word in ["charge", "assault", "attack"]) and random.random() < 0.3:
            # Higher risk actions can lead to casualties
            casualty = random.choice(squad)
            events.append(f"CASUALTY: {casualty} is wounded and evacuated!")
            squad.remove(casualty)
            session["squad"] = squad
            session["squad_casualties"] = session.get("squad_casualties", []) + [casualty]
        else:
            # Positive squad events
            squad_member = random.choice(squad)
            squad_events = [
                f"{squad_member} provides excellent covering fire!",
                f"{squad_member} spots enemy movement ahead.",
                f"{squad_member} secures the flank position."
            ]
            events.append(random.choice(squad_events))
    
    # Resource management events
    if turn_count > 2 and random.random() < 0.25:
        resource_events = [
            "You find enemy ammunition supplies.",
            "A wounded enemy drops medical supplies.", 
            "You discover abandoned equipment."
        ]
        if random.random() < 0.5:
            resource_type = random.choice(["ammo", "medkit", "grenade"])
            amount = random.randint(1, 3)
            resources[resource_type] = resources.get(resource_type, 0) + amount
            events.append(f"Found {amount} {resource_type}{'s' if amount > 1 else ''}!")
    
    return " ".join(events) if events else ""

# Combat function moved to game_logic.py
        
    

@app.route("/")
def index():
    """Character creation and game start page."""
    # Load existing data from database
    load_from_database()
    
    # Initialize player stats if not present
    if "player_stats" not in session:
        session["player_stats"] = initialize_player_stats()
    
    return render_template("index.html", 
                         ranks=RANKS, 
                         classes=CLASSES, 
                         weapons=WEAPONS,
                         achievements_count=len(session.get("player_stats", {}).get("achievements_unlocked", [])))

@app.route("/create_character", methods=["POST"])
def create_character():
    """Process character creation form."""
    # Preserve player stats across character creation
    player_stats = session.get("player_stats", initialize_player_stats())
    session.clear()
    session["player_stats"] = player_stats
    
    # Clear any pending combat flags
    session.pop("combat_pending", None)
    
    # Create player character with enhanced attributes
    player_class = request.form.get("char_class", "Rifleman")
    weapon = request.form.get("weapon", "Rifle")
    
    # Class-specific special abilities
    special_abilities = {
        "Rifleman": "Squad Leader - Boosts squad morale and coordination",
        "Medic": "Field Medicine - Can heal wounded squad members quickly",
        "Gunner": "Suppressing Fire - Can pin down multiple enemies",
        "Sniper": "Precision Shot - One-shot elimination of priority targets",
        "Demolitions": "Explosive Expert - Double damage with grenades and charges"
    }
    
    session["player"] = {
        "name": request.form.get("name", "Rookie").strip() or "Rookie",
        "rank": request.form.get("rank", "Private"),
        "class": player_class,
        "weapon": weapon,
        "health": 100,
        "max_health": 100,
        "morale": 100,
        "experience": 0,
        "special_ability": special_abilities.get(player_class, "Standard Training")
    }
    
    # Update achievement stats
    session["player_stats"] = update_player_stats(
        session["player_stats"], 
        "class_selected", 
        class_name=player_class
    )
    
    # Class-specific resource bonuses
    base_resources = {"medkit": 2, "grenade": 2, "ammo": 12, "intel": 0}
    
    if player_class == "Medic":
        base_resources["medkit"] += 2
    elif player_class == "Gunner":
        base_resources["ammo"] += 8
    elif player_class == "Demolitions":
        base_resources["grenade"] += 3
    elif player_class == "Sniper":
        base_resources["ammo"] += 4
    else:  # Rifleman
        base_resources["ammo"] += 3
        base_resources["medkit"] += 1
    
    session["resources"] = base_resources
    
    # Generate dynamic squad with varied specializations 
    # Check if we have wounded from previous missions
    wounded_members = session.get("squad_casualties", [])
    
    all_squad_members = [
        "Thompson (Rifleman)", "Garcia (Medic)", "Kowalski (Gunner)",
        "Anderson (Sniper)", "Martinez (Demo)", "Chen (Scout)", 
        "O'Brien (Engineer)", "Williams (Radio)", "Jackson (Veteran)",
        "Murphy (Corpsman)", "Rodriguez (Assault)", "Singh (Marksman)"
    ]
    
    # Remove wounded members from available pool
    available_members = [m for m in all_squad_members if m not in wounded_members]
    
    # If we have existing squad, keep survivors and add replacements
    existing_squad = session.get("squad", [])
    if existing_squad:
        # Keep existing survivors
        survivors = [m for m in existing_squad if m not in wounded_members]
        needed = max(3, 5 - len(survivors))  # Ensure minimum squad size
        
        # Add replacements for wounded
        replacements = [m for m in available_members if m not in survivors]
        if replacements:
            new_recruits = random.sample(replacements, min(needed, len(replacements)))
            session["squad"] = survivors + new_recruits
        else:
            session["squad"] = survivors
    else:
        # First mission - create new squad
        squad_size = random.randint(3, 5)
        session["squad"] = random.sample(available_members, min(squad_size, len(available_members)))
    
    # Clear casualties after new character creation (they've recovered/been replaced)
    session["squad_casualties"] = []
    
    # Game progress tracking
    session["completed"] = []
    session["score"] = 0
    session["missions_completed"] = 0
    session["battles_won"] = 0
    
    logging.info(f"Character created: {session['player']['name']}")
    return redirect(url_for("mission_menu"))

@app.route("/missions")
def mission_menu():
    """Display campaign missions - starts with D-Day, then AI generates next missions."""
    if "player" not in session:
        return redirect(url_for("create_character"))
    
    # Initialize campaign if not exists
    if "campaign" not in session:
        session["campaign"] = {
            "current_mission": 0,
            "generated_missions": [],
            "completed_missions": [],
            "campaign_date": "June 6, 1944"
        }
    
    campaign = session["campaign"]
    current_mission_num = campaign["current_mission"]
    
    # Get current mission
    if current_mission_num == 0:
        # First mission is always D-Day
        current_mission = INITIAL_MISSION
    else:
        # Get AI-generated mission
        generated = campaign.get("generated_missions", [])
        if current_mission_num - 1 < len(generated):
            current_mission = generated[current_mission_num - 1]
        else:
            # Generate next mission if not available
            current_mission = generate_next_mission()
            campaign["generated_missions"].append(current_mission)
            session["campaign"] = campaign
    
    # Get persistent squad state
    squad = session.get("squad", [])
    dead_squad = session.get("dead_squad_members", [])
    
    # Calculate achievements count for template
    player_stats = session.get("player_stats", initialize_player_stats())
    achievements_count = len(player_stats.get("achievements_unlocked", []))
    
    return render_template("missions.html", 
                         mission=current_mission,
                         mission_number=current_mission_num + 1,
                         squad=squad,
                         dead_squad=dead_squad,
                         player=session.get("player"),
                         score=session.get("score", 0),
                         campaign_date=campaign.get("campaign_date"),
                         achievements_count=achievements_count)

@app.route("/start_mission", methods=["POST"])
def start_mission():
    """Initialize selected mission."""
    print("=== START_MISSION ROUTE CALLED ===")  # Use print for immediate output
    logging.info("=== START_MISSION ROUTE CALLED ===")
    chosen_mission = request.form.get("mission")
    print(f"Chosen mission: {chosen_mission}")
    logging.info(f"Chosen mission: {chosen_mission}")
    
    # Get mission from campaign system
    campaign = session.get("campaign", {})
    current_mission_num = campaign.get("current_mission", 0)
    
    if current_mission_num == 0:
        mission = INITIAL_MISSION
    else:
        generated = campaign.get("generated_missions", [])
        if current_mission_num - 1 < len(generated):
            mission = generated[current_mission_num - 1]
        else:
            mission = INITIAL_MISSION
    
    # Store mission data in cloud storage instead of session
    set_game_state({
        "mission": mission,
        "turn_count": 0,
        "story_history": [],
        "mission_phase": "start",
        "resources": session.get("resources", {}),
        "squad": session.get("squad", [])
    })
    
    # Store player data in cloud storage
    set_player_data(session.get("player", {}))
    
    # Use enhanced session management
    session_manager.auto_cleanup()
    
    # Mission briefing reward
    resources = session.get("resources", {})
    resources["ammo"] = resources.get("ammo", 0) + 3
    session["resources"] = resources
    
    # Get player and squad data (might be in session or cloud storage)
    player = session.get("player", {})
    if not player:
        player = get_player_data({})
    
    squad = session.get("squad", [])
    logging.info(f"Retrieved player: {player.get('name', 'Unknown')} and squad: {len(squad)} members")
    
    # Generate initial mission scenario with enhanced prompting
    system_msg = (
        "You are a master WWII text-adventure game narrator. Create an immersive opening scenario that:"
        "- Sets a vivid, authentic WWII battlefield atmosphere"
        "- Establishes clear stakes and mission urgency"
        "- Mentions the player's military details naturally"
        "- Builds tension and immersion"
        "- ALWAYS ends with exactly 3 numbered tactical choices (format: 1. [action])"
        "- Each choice should feel meaningfully different"
        "- Keep the scenario focused and engaging (2-3 paragraphs max)"
    )
    
    user_prompt = (
        f"MISSION START: {mission['name']} ({mission['difficulty']} difficulty)\n"
        f"Objective: {mission['desc']}\n\n"
        f"Player: {player.get('rank')} {player.get('name')}, {player.get('class')} with {player.get('weapon')}\n"
        f"Squad: {', '.join(squad) if squad else 'Solo mission'}\n\n"
        "Create an engaging opening scenario that establishes the mission context and provides 3 tactical choices."
    )
    
    print("Generating story content...")
    logging.info("Generating story content...")
    # Temporary: Use a simple test story to debug session management
    story = "The beaches of Normandy stretch before you as dawn breaks on June 6, 1944. Your squad is ready for the assault. The enemy positions are fortified but victory depends on your tactical choices.\n\n1. Storm the beach with aggressive fire and movement.\n2. Use covering fire and advance by sections.\n3. Look for alternative routes up the bluff."
    print(f"Using test story: '{story[:100]}...' ({len(story)} characters)")
    logging.info(f"Using test story: '{story[:100]}...' ({len(story)} characters)")
    
    # Initialize clean session for new mission - temporarily use Flask session for immediate fix
    print(f"Setting story data: {len(story)} characters")
    logging.info(f"Setting story data: {len(story)} characters")
    session["story"] = story  # Temporary: use Flask session to fix immediate issue
    success = set_story_data(story)  # Also try cloud storage
    print(f"Story data set successfully: Flask={bool(session.get('story'))}, Cloud={success}")
    logging.info(f"Story data set successfully: Flask={bool(session.get('story'))}, Cloud={success}")
    # Move these to cloud storage to reduce session size
    # session["base_story"] = ""  # Reset base story
    # session["new_content"] = ""  # Reset new content  
    # session["turn_count"] = 0  # Reset turn counter
    # session["story_history"] = [{"turn": 0, "content": story, "type": "start"}]  # Fresh history
    
    # Clear large data from Flask session to prevent overflow
    for key in ['squad', 'resources', 'player', 'mission', 'campaign', 'story_history']:
        session.pop(key, None)
    
    print(f"Session keys after cleanup: {list(session.keys())}")
    
    print(f"Mission started: {mission['name']}")
    logging.info(f"Mission started: {mission['name']}")
    print("Testing story retrieval immediately...")
    
    # Test immediate retrieval to see if redirect is the issue
    test_story = session.get("story", "")
    test_cloud = get_story_data("")
    print(f"Immediate test - Flask: {len(test_story)}, Cloud: {len(test_cloud)}")
    
    if test_story:
        # If we have story data, render play directly instead of redirecting
        choices = parse_choices(test_story)
        game_state = get_game_state({})
        player_data = get_player_data({})
        
        print("Rendering play template directly...")
        return render_template("play.html", 
                             story=test_story,
                             base_story="",
                             new_content="",
                             choices=choices,
                             player=player_data, 
                             resources=game_state.get("resources", {}),
                             mission=game_state.get("mission", {}),
                             turn_count=game_state.get("turn_count", 0),
                             squad=game_state.get("squad", []))
    else:
        print("No story found, redirecting to missions...")
        return redirect(url_for("mission_menu"))

@app.route("/play")
def play():
    """Main gameplay interface."""
    print("=== PLAY ROUTE CALLED ===")
    # Try cloud storage first, fall back to Flask session
    story = get_story_data("")
    if not story:
        story = session.get("story", "")
        print(f"Using Flask session fallback: {len(story)} characters")
    print(f"Play route: story length = {len(story) if story else 0}")
    logging.info(f"Play route: story length = {len(story) if story else 0}")
    if not story:
        print("No story data found, redirecting to missions")
        logging.warning("No story data found, redirecting to missions")
        return redirect(url_for("mission_menu"))
    
    choices = parse_choices(story)
    
    # Progressive story display: separate base story from new content
    base_story = session.get("base_story", "")
    new_content = session.get("new_content", "")
    
    # Get game data from cloud storage
    game_state = get_game_state({})
    player_data = get_player_data({})
    
    return render_template("play.html", 
                         story=story,
                         base_story=base_story,
                         new_content=new_content,
                         choices=choices,
                         player=player_data, 
                         resources=game_state.get("resources", {}),
                         mission=game_state.get("mission", {}),
                         turn_count=game_state.get("turn_count", 0),
                         squad=game_state.get("squad", []))

@app.route("/make_choice", methods=["POST"])
@app.route("/choose", methods=["POST"])
def make_choice():
    """Process player's choice and continue story."""
    try:
        # Input validation and sanitization
        choice_input = request.form.get("choice", "1").strip()
        if not choice_input.isdigit():
            choice_input = "1"
        choice_index = max(0, min(2, int(choice_input) - 1))  # Clamp to valid range
        
        # Get current story and parse fresh choices
        current_story = get_story_data("")
        choices = parse_choices(current_story)
        if 0 <= choice_index < len(choices):
            chosen_action = choices[choice_index]
        else:
            chosen_action = choices[0] if choices else "Continue forward."
        
        # Increment turn counter and update mission phase
        turn_count = session.get("turn_count", 0) + 1
        session["turn_count"] = turn_count
        
        # Determine mission phase based on turn count
        if turn_count <= 2:
            session["mission_phase"] = "middle"
        elif turn_count <= 4:
            session["mission_phase"] = "climax"
        else:
            session["mission_phase"] = "end"
        
        logging.info(f"Turn {turn_count}: Player chose option {choice_index + 1}: {chosen_action}")
        
        # Update achievement stats for choice made
        player_stats = session.get("player_stats", initialize_player_stats())
        session["player_stats"] = update_player_stats(player_stats, "choice_made")
        
        # Store the choice separately for progressive display
        session["last_choice"] = chosen_action
        
        # Progressive story management
        base_story = session.get("base_story", "")
        
        # On first turn, set the base story
        if turn_count == 1:
            session["base_story"] = current_story
            base_story = current_story
        elif not base_story:
            # Fallback for missing base story
            session["base_story"] = current_story
            base_story = current_story
        
        # Initialize story variable for compatibility
        story = current_story + f"\n\n> You chose: {chosen_action}\n"
        
        # Enhanced mission completion detection
        completion_keywords = ["return to base", "exfiltrate", "mission complete", "objective secured", "fall back", "retreat", "withdraw"]
        success_keywords = ["bridge destroyed", "prisoners freed", "documents secured", "tower captured", "supplies secured", "objective complete"]
        
        # Check for explicit completion choices
        if any(keyword in chosen_action.lower() for keyword in completion_keywords):
            return complete_mission(story)
        
        # Auto-complete after 6 turns to prevent infinite games
        mission = session.get("mission", {})
        if turn_count >= 6:
            mission_name = mission.get("name", "").lower()
            if "sabotage" in mission_name:
                completion_story = "\n\nWith the charges set and the area clear, you signal the detonation. The bridge collapses in a thunderous explosion, cutting off enemy supply lines. Mission accomplished!"
            elif "rescue" in mission_name:
                completion_story = "\n\nAfter fierce fighting, you successfully extract the prisoners and reach the extraction point. The POWs are safe. Mission accomplished!"
            elif "intel" in mission_name:
                completion_story = "\n\nWith the classified documents secured, you make your way to the extraction point. The intelligence will prove invaluable. Mission accomplished!"
            else:
                completion_story = "\n\nAfter sustained combat operations, you have achieved the mission objectives and successfully return to base. Mission accomplished!"
            
            return complete_mission(story + completion_story)
        
        # Apply dynamic choice consequences
        player = session.get("player", {})
        resources = session.get("resources", {})
        mission = session.get("mission", {})
        squad = session.get("squad", [])
        
        # Enhanced consequence system
        consequence_events = generate_dynamic_consequences(
            chosen_action, player, resources, mission, turn_count
        )
        
        # Apply consequences to story
        if consequence_events:
            story += "\n" + consequence_events
        
        # Check if player died
        if player.get("health", 0) <= 0:
            player_stats = session.get("player_stats", initialize_player_stats())
            session["player_stats"] = update_player_stats(player_stats, "player_death")
            story += "\n--- MISSION FAILED ---\nYou have been critically wounded and the mission is aborted."
            set_story_data(story)
            return redirect(url_for("base_camp"))
        
        # Enhanced story generation with context
        mission_phase = session.get("mission_phase", "middle")
        mission = session.get("mission", {})
        
        # Build narrative context from story history
        story_context = ""
        story_history = session.get("story_history", [])
        if len(story_history) > 1:
            # Get key plot points from recent history
            recent_choices = []
            for entry in story_history[-3:]:  # Last 3 turns
                if entry.get("choice") and entry.get("type") != "compressed":
                    recent_choices.append(entry["choice"][:80])  # Truncate for brevity
            
            if recent_choices:
                story_context = f"Recent actions: {' -> '.join(recent_choices)}. "
        
        # Extract mission objectives for continuity
        mission_objectives = ""
        mission_name = mission.get('name', '').lower()
        if "sabotage" in mission_name:
            mission_objectives = "Objective: Destroy the target structure. "
        elif "rescue" in mission_name:
            mission_objectives = "Objective: Extract prisoners safely. "
        elif "intel" in mission_name:
            mission_objectives = "Objective: Secure classified documents. "
        
        # Dynamic system message based on mission phase
        if mission_phase == "middle":
            phase_instruction = "Develop the mission further. Introduce challenges, obstacles, or tactical situations that test the player's decisions."
        elif mission_phase == "climax":
            phase_instruction = "Build toward the mission climax. Increase tension and make stakes higher. The objective should be within reach but challenging."
        else:  # end phase
            phase_instruction = "Move toward mission completion. Provide opportunities to complete the objective or create final dramatic moments."
        
        system_msg = (
            f"You are a WWII text adventure narrator. Continue the story based on the player's choice. "
            f"CONTEXT: {story_context}{mission_objectives}"
            f"REQUIREMENTS: "
            f"1. Show immediate consequences of the player's choice: {chosen_action} "
            f"2. This is turn {turn_count} of mission: {mission.get('name')} "
            f"3. {phase_instruction} "
            f"4. Maintain narrative continuity with previous actions. "
            f"5. ALWAYS end with exactly 3 numbered tactical choices like this: "
            f"1. [specific action] "
            f"2. [different action] "
            f"3. [alternative action] "
            f"6. Keep choices concrete and tactical, not vague. "
            f"7. Write 2-3 paragraphs then provide the 3 choices."
        )
        
        user_prompt = (
            f"Player chose: {chosen_action}\n"
            f"Mission: {mission.get('name')}\n"
            f"Player: {player.get('name')} ({player.get('class')}) - Health: {player.get('health', 100)}\n"
            f"Continue the story showing what happens after this choice."
        )
        
        # Use story manager for story generation if available
        if hasattr(story_manager, 'generate_story_continuation'):
            new_content = story_manager.generate_story_continuation(
                mission, player, story, chosen_action
            )
        else:
            new_content = ai_chat(system_msg, user_prompt)
        logging.info(f"Generated content: {new_content[:200]}...")
        
        # Check for success indicators in AI response after generation
        if any(keyword in new_content.lower() for keyword in SUCCESS_KEYWORDS):
            return complete_mission(story + f"\n\nMISSION OBJECTIVE ACHIEVED: {chosen_action}")
        
        # COMBAT DETECTION - Check for combat keywords and set flag for frontend interactive combat
        combat_detected = any(keyword in new_content.lower() for keyword in COMBAT_KEYWORDS)
        
        # Debug logging to track detection
        logging.info(f"Combat detection check: content length={len(new_content)}, keywords_matched={[k for k in COMBAT_KEYWORDS if k in new_content.lower()]}")
        
        if combat_detected:
            # Use Replit Key-Value Store for combat data - no cookie limits!
            replit_session.set_data("combat_pending", True)
            replit_session.set_data("combat_story_content", new_content)
            
            # Also set minimal flag in session for immediate frontend access
            session["combat_pending"] = True
            
            logging.warning(f"🔥 COMBAT DETECTED! Keywords found: {[k for k in COMBAT_KEYWORDS if k in new_content.lower()]}")
            logging.info("Combat data stored in Replit Key-Value Store - no cookie limits!")
            
            # Don't auto-resolve combat here - let the frontend handle it
        else:
            # No combat detected, clear any pending combat flags
            replit_session.delete_data("combat_pending")
            replit_session.delete_data("combat_story_content")
            session.pop("combat_pending", None)
            logging.info("No combat detected in current content")
        
        # Only parse and add choices if combat is NOT detected
        if not combat_detected:
            # Parse choices from the new content immediately
            fresh_choices = parse_choices(new_content)
            logging.info(f"Parsed choices: {fresh_choices}")
            
            # If no valid choices found, add fallback choices to the content
            if len(fresh_choices) < 3:
                fallback_choices = generate_contextual_choices(player, mission, turn_count)
                choices_text = f"\n\n1. {fallback_choices[0]}\n2. {fallback_choices[1]}\n3. {fallback_choices[2]}"
                new_content += choices_text
                logging.info(f"Added fallback choices: {fallback_choices}")
        else:
            logging.info("Combat detected - skipping choice generation, combat system will handle flow")
        
        # Initialize choice_result regardless of combat detection
        choice_result = f"\n\n> You chose: {chosen_action}\n\n{new_content}"
        
        # Don't update story immediately if combat is pending - wait for combat resolution
        if not combat_detected:
            # Save story turn to database instead of session
            from game_logic import get_session_id
            session_id = get_session_id()
            db.save_story_turn(session_id, turn_count, chosen_action, new_content)
            
            # Progressive story system: only show new content typing
            session["new_content"] = choice_result
        else:
            # Combat detected - don't show new content yet, let combat system handle it
            session["pending_choice_result"] = choice_result
            logging.info("Combat detected - story update delayed until combat resolution")
        
        # Update the full story for next iteration - this is critical for choice parsing
        if not combat_detected:
            new_full_story = base_story + choice_result
        else:
            # Keep current story state until combat is resolved
            new_full_story = base_story + session.get("pending_choice_result", "")
        
        # Check for mission outcome after story update
        mission_outcome = detect_mission_outcome(new_full_story)
        if mission_outcome:
            session["mission_outcome"] = mission_outcome
            
            # Update squad casualties based on story content
            if any(word in new_content.lower() for word in ["casualty", "killed", "died", "fallen", "lost"]):
                squad = session.get("squad", [])
                if squad and random.random() < 0.3:  # 30% chance of squad casualty
                    casualty = random.choice(squad)
                    squad.remove(casualty)
                    session["squad"] = squad
                    
                    dead_members = session.get("dead_squad_members", [])
                    dead_members.append(casualty)
                    session["dead_squad_members"] = dead_members
                    
                    # Add to story
                    new_full_story += f"\n\n[Squad member {casualty} has fallen in combat.]"
            
            # Mission complete - redirect to base camp
            if mission_outcome == "success":
                session["story"] = new_full_story + "\n\nMISSION SUCCESSFUL! Returning to base..."
                return redirect(url_for("mission_complete"))
            elif mission_outcome == "failure":
                session["story"] = new_full_story + "\n\nMISSION FAILED. Forced to retreat..."
                return redirect(url_for("mission_complete"))
        
        # Hybrid session-database story management
        if len(new_full_story) > 2500:  # Lower threshold with database backup
            from game_logic import get_session_id
            session_id = get_session_id()
            
            # Store full story in database before compression
            db.save_story_chunk(session_id, f"full_story_turn_{turn_count}", new_full_story)
            
            # Create intelligent summary with key plot points
            mission = session.get("mission", {})
            player = session.get("player", {})
            
            # Extract key points for better summarization
            key_points = [
                player.get("name", ""),
                player.get("class", ""),
                mission.get("name", ""),
                chosen_action[:50]  # Recent choice
            ]
            
            # Use database method for compression
            summarized_story = db.create_story_summary_db(session_id, new_full_story, key_points)
            
            # Keep minimal data in session
            session["base_story"] = summarized_story
            set_story_data(summarized_story + choice_result)
            session["story_compressed"] = True
            session["story_turn_compressed"] = turn_count
            
            # Log compression statistics
            compression_ratio = len(summarized_story) / len(new_full_story)
            logging.info(f"Story compressed: {len(new_full_story)} -> {len(summarized_story)} chars (ratio: {compression_ratio:.2f})")
        
        else:
            # Keep normal session-based story management
            set_story_data(new_full_story)
            session["story"] = new_full_story  # Also store in Flask session for immediate access
            session["base_story"] = base_story
        
        # Update session and save to database
        session["player"] = player
        session["resources"] = resources
        save_to_database()
        
        # Render play directly instead of redirecting to avoid session loss
        choices = parse_choices(new_full_story)
        game_state = get_game_state({})
        player_data = get_player_data({})
        
        return render_template("play.html", 
                             story=new_full_story,
                             base_story=base_story,
                             new_content="",
                             choices=choices,
                             player=player_data, 
                             resources=game_state.get("resources", {}),
                             mission=game_state.get("mission", {}),
                             turn_count=turn_count,
                             squad=game_state.get("squad", []))
    
    except Exception as e:
        logging.error(f"Error in story management: {e}")
        # Fallback to simple story management with safe defaults
        try:
            current_story = session.get("story", "")
            base_story_safe = session.get("base_story", "")
            action_text = locals().get("chosen_action", "a tactical action")
            new_full_story_safe = base_story_safe + f"\n\n> You chose: {action_text}\n\nThe mission continues..."
            
            set_story_data(new_full_story_safe)
            session["base_story"] = base_story_safe
        except Exception as fallback_error:
            logging.error(f"Fallback error: {fallback_error}")
            set_story_data("Mission continues...")
        
        # Ensure we always return a response
        return redirect(url_for("play"))


@app.route("/recover_story", methods=["POST"])
def recover_story():
    """Recover full story from database if needed."""
    try:
        session_id = get_session_id()
        turn_number = request.form.get("turn", session.get("turn_count", 0))
        
        # Try to recover full story from database
        full_story = db.get_story_chunk(session_id, f"full_story_turn_{turn_number}")
        
        if full_story:
            # Temporarily expand story for player review
            session["story"] = full_story
            session["story_recovered"] = True
            
            return jsonify({
                "success": True,
                "message": "Full story recovered from database",
                "story_length": len(full_story)
            })
        else:
            return jsonify({
                "success": False,
                "message": "No stored story found for this turn"
            })
            
    except Exception as e:
        logging.error(f"Story recovery error: {e}")
        return jsonify({
            "success": False,
            "message": "Story recovery failed"
        })

@app.route("/story_analytics")
def story_analytics():
    """Show story compression analytics."""
    if "player" not in session:
        return redirect(url_for("index"))
    
    session_id = get_session_id()
    
    # Get compression statistics
    analytics = {
        "current_turn": session.get("turn_count", 0),
        "story_compressed": session.get("story_compressed", False),
        "compression_turn": session.get("story_turn_compressed", 0),
        "session_story_length": len(session.get("story", "")),
        "base_story_length": len(session.get("base_story", "")),
        "available_chunks": []
    }
    
    # Get available story chunks from database  
    try:
        # Simplified version to avoid LSP type issues
        analytics["available_chunks"] = []  # Placeholder for now
        logging.info("Story analytics simplified for stability")
        
    except Exception as e:
        logging.error(f"Analytics error: {e}")
        analytics["available_chunks"] = []
    
    return jsonify(analytics)

def complete_mission(story):
    """Handle enhanced mission completion with dynamic outcomes."""
    mission = session.get("mission", {})
    player = session.get("player", {})
    resources = session.get("resources", {})
    turn_count = session.get("turn_count", 0)
    story_history = session.get("story_history", [])
    
    difficulty_mod = get_difficulty_modifier(mission.get("difficulty", "Medium"))
    
    # Calculate dynamic mission outcome based on performance
    mission_outcome = calculate_mission_outcome(player, resources, turn_count, story_history, difficulty_mod)
    
    # Award score based on performance factors
    base_score = difficulty_mod["reward"]
    health_bonus = max(0, player.get("health", 0) - 50)
    stealth_bonus = mission_outcome.get("stealth_bonus", 0)
    efficiency_bonus = mission_outcome.get("efficiency_bonus", 0)
    
    total_score = base_score + health_bonus + stealth_bonus + efficiency_bonus
    
    session["score"] = session.get("score", 0) + total_score
    session["missions_completed"] = session.get("missions_completed", 0) + 1
    
    # Add to completed missions with outcome rating
    completed = session.get("completed", [])
    mission_name = mission.get("name")
    if mission_name not in completed:
        completed.append(mission_name)
        session["completed"] = completed
    
    # Store mission performance for future reference
    session["mission_outcomes"] = session.get("mission_outcomes", {})
    session["mission_outcomes"][mission_name] = mission_outcome
    
    # Update achievement stats
    session["player_stats"] = update_player_stats(
        session["player_stats"], 
        "mission_completed", 
        score=total_score
    )
    
    # Check for new achievements
    new_achievements = check_achievements(session["player_stats"])
    new_achievement_displays = []
    if new_achievements:
        unlocked = session["player_stats"].get("achievements_unlocked", [])
        for achievement_id in new_achievements:
            if achievement_id not in unlocked:
                unlocked.append(achievement_id)
                new_achievement_displays.append(get_achievement_display(achievement_id))
        session["player_stats"]["achievements_unlocked"] = unlocked
    
    # Prepare debrief data
    bonuses = []
    if health_bonus > 0:
        bonuses.append({"name": "Health Bonus", "value": health_bonus})
    if stealth_bonus > 0:
        bonuses.append({"name": "Stealth Operations", "value": stealth_bonus})
    if efficiency_bonus > 0:
        bonuses.append({"name": "Tactical Efficiency", "value": efficiency_bonus})
    
    # Create mission highlights from story events
    mission_highlights = []
    for story_entry in story_history[-3:]:  # Last 3 story entries
        if story_entry.get("type") == "continuation" and story_entry.get("choice"):
            mission_highlights.append(f"Executed: {story_entry['choice']}")
    
    # Add special highlights based on mission outcome
    if mission_outcome.get("special_notes"):
        mission_highlights.extend(mission_outcome["special_notes"])
    
    # Squad casualties from this mission
    squad_casualties = session.get("squad_casualties", [])
    
    # Store debrief data
    session["debrief_data"] = {
        "mission": mission,
        "mission_success": True,
        "mission_outcome": mission_outcome,
        "score_earned": total_score,
        "bonuses": bonuses,
        "mission_highlights": mission_highlights,
        "new_achievements": new_achievement_displays,
        "squad_casualties": squad_casualties,
        "turn_count": turn_count
    }
    
    return redirect(url_for("mission_debrief"))

def calculate_mission_outcome(player: dict, resources: dict, turn_count: int, story_history: list, difficulty_mod: dict) -> dict:
    """Calculate mission outcome based on player performance."""
    outcome = {
        "rating": "Standard",
        "stealth_bonus": 0,
        "efficiency_bonus": 0,
        "special_notes": [],
        "description": "Mission objectives achieved through standard military operations."
    }
    
    # Health performance
    health_percent = player.get("health", 100) / 100
    if health_percent > 0.8:
        outcome["rating"] = "Exceptional"
        outcome["efficiency_bonus"] += 50
        outcome["special_notes"].append("completed with minimal casualties")
    elif health_percent > 0.5:
        outcome["rating"] = "Good"

        outcome["efficiency_bonus"] += 25
    
    # Turn efficiency (completing quickly)
    if turn_count <= 3:
        outcome["efficiency_bonus"] += 30
        outcome["special_notes"].append("executed with tactical precision")
    elif turn_count <= 5:
        outcome["efficiency_bonus"] += 15
    
    # Resource management
    total_resources = sum(resources.values())
    if total_resources > 8:
        outcome["stealth_bonus"] += 20
        outcome["special_notes"].append("excellent resource conservation")
    
    # Class-specific bonuses from story choices
    player_class = player.get("class", "Rifleman")
    class_achievements = {
        "Medic": "provided critical medical support",
        "Sniper": "eliminated key targets with precision", 
        "Gunner": "provided devastating fire support",
        "Demolitions": "destroyed strategic objectives",
        "Rifleman": "demonstrated exceptional leadership"
    }
    
    if random.random() < 0.4:  # 40% chance for class-specific recognition
        outcome["special_notes"].append(class_achievements.get(player_class, "showed tactical skill"))
    
    # Generate outcome description
    if outcome["rating"] == "Exceptional":
        outcome["description"] = f"Outstanding performance! Mission completed with minimal casualties and exceptional tactical execution."
    elif outcome["rating"] == "Good":
        outcome["description"] = f"Solid performance. Objectives achieved with good tactical awareness and effective leadership."
    else:
        outcome["description"] = "Mission objectives achieved through standard military operations."
    
    return outcome

def generate_mission_completion_text(outcome: dict, total_score: int) -> str:
    """Generate dynamic mission completion text."""
    rating = outcome["rating"]
    notes = outcome["special_notes"]
    
    rating_messages = {
        "Exceptional": "--- MISSION SUCCESS: EXCEPTIONAL PERFORMANCE ---",
        "Good": "--- MISSION SUCCESS: GOOD PERFORMANCE ---",
        "Standard": "--- MISSION COMPLETE ---"
    }
    
    completion_text = rating_messages.get(rating, "--- MISSION COMPLETE ---")
    
    if notes:
        completion_text += f"\n\nSpecial Recognition: {', '.join(notes).capitalize()}."
    
    completion_text += f"\n\nScore earned: {total_score} points"
    
    if outcome["efficiency_bonus"] > 0:
        completion_text += f"\nEfficiency bonus: +{outcome['efficiency_bonus']}"
    if outcome["stealth_bonus"] > 0:
        completion_text += f"\nStealth bonus: +{outcome['stealth_bonus']}"
    
    return completion_text

@app.route("/debrief")
def mission_debrief():
    """Display mission debrief with detailed recap."""
    debrief_data = session.get("debrief_data")
    if not debrief_data:
        return redirect(url_for("mission_menu"))
    
    # Get current game state
    player = session.get("player", {})
    resources = session.get("resources", {})
    squad = session.get("squad", [])
    
    # Get achievements count
    player_stats = session.get("player_stats", {})
    achievements_count = len(player_stats.get("achievements_unlocked", []))
    
    return render_template("debrief.html",
                         **debrief_data,
                         player=player,
                         resources=resources,
                         squad=squad,
                         achievements_count=achievements_count)

@app.route("/mission_complete")
def mission_complete():
    """Handle mission completion and transition to next mission."""
    if "mission" not in session:
        return redirect(url_for("mission_menu"))
    
    mission = session.get("mission", {})
    mission_outcome = session.get("mission_outcome", "completed")
    campaign = session.get("campaign", {})
    
    # Record mission in campaign history
    completed_mission = {
        "name": mission.get("name"),
        "outcome": mission_outcome,
        "casualties": session.get("dead_squad_members", [])[-1:],  # Last casualty if any
        "turn_count": session.get("turn_count", 0)
    }
    
    campaign.setdefault("completed_missions", []).append(completed_mission)
    
    # Advance campaign if successful
    if mission_outcome == "success":
        campaign["current_mission"] = campaign.get("current_mission", 0) + 1
        session["score"] = session.get("score", 0) + 100
        session["missions_completed"] = session.get("missions_completed", 0) + 1
        # Enable camping after successful missions
        session["can_camp"] = True
    
    session["campaign"] = campaign
    
    # Clean up mission-specific data but keep persistent data
    session.pop("story", None)
    session.pop("base_story", None)
    session.pop("new_content", None)
    session.pop("story_history", None)
    session.pop("turn_count", None)
    session.pop("mission_outcome", None)
    session.pop("mission_phase", None)
    
    return render_template("mission_complete.html",
                         mission=mission,
                         outcome=mission_outcome,
                         player=session.get("player"),
                         squad=session.get("squad", []),
                         dead_squad=session.get("dead_squad_members", []),
                         score=session.get("score", 0))

@app.route("/base")
def base_camp():
    """Base camp summary page.""" 
    # Check for new achievements to display
    new_achievements = session.pop("new_achievements", [])
    
    return render_template("base.html",
                         player=session.get("player"),
                         score=session.get("score", 0),
                         missions_completed=session.get("missions_completed", 0),
                         battles_won=session.get("battles_won", 0),
                         completed=session.get("completed", []),
                         new_achievements=new_achievements)

@app.route("/achievements")
def achievements():
    """Display achievements page."""
    player_stats = session.get("player_stats", initialize_player_stats())
    unlocked_ids = player_stats.get("achievements_unlocked", [])
    
    # Prepare achievement data for template
    achievements_data = []
    for achievement_id, achievement_info in ACHIEVEMENTS.items():
        display_data = get_achievement_display(achievement_id)
        display_data["unlocked"] = str(achievement_id in unlocked_ids)
        achievements_data.append(display_data)
    
    # Check for newly unlocked achievements
    new_achievement_ids = check_achievements(player_stats)
    new_achievements = []
    if new_achievement_ids:
        for aid in new_achievement_ids:
            if aid not in unlocked_ids:
                unlocked_ids.append(aid)
                new_achievements.append(get_achievement_display(aid))
        
        # Update session with newly unlocked achievements
        player_stats["achievements_unlocked"] = unlocked_ids
        session["player_stats"] = player_stats
    
    return render_template("achievements.html",
                         achievements=achievements_data,
                         new_achievements=new_achievements,
                         player_stats=player_stats)

@app.route("/use_item", methods=["POST"])
def use_item():
    """Handle item usage during gameplay."""
    item_type = request.form.get("item")
    player = session.get("player", {})
    resources = session.get("resources", {})
    
    if item_type == "medkit" and resources.get("medkit", 0) > 0:
        max_health = player.get("max_health", 100)
        if player.get("health", 100) < max_health:
            # Class-specific healing bonuses
            heal_amount = 30
            if player.get("class") == "Medic":
                heal_amount = 45  # Medics are more efficient
            
            player["health"] = min(max_health, player.get("health", 100) + heal_amount)
            resources["medkit"] -= 1
            
            # Boost morale when healing
            player["morale"] = min(100, player.get("morale", 100) + 10)
            
            # Update achievement stats
            player_stats = session.get("player_stats", initialize_player_stats())
            session["player_stats"] = update_player_stats(player_stats, "item_used")
            
            session["player"] = player
            session["resources"] = resources
            
            return jsonify({
                "success": True,
                "message": f"Medkit used! Restored {heal_amount} health.",
                "health": player["health"],
                "morale": player["morale"]
            })
        else:
            return jsonify({
                "success": False,
                "message": "You are already at full health."
            })
    
    elif item_type == "grenade" and resources.get("grenade", 0) > 0:
        resources["grenade"] -= 1
        session["resources"] = resources
        
        # Class-specific grenade effects
        effect_msg = "Grenade thrown! Enemy position compromised."
        if player.get("class") == "Demolitions":
            effect_msg = "Enhanced explosive! Devastating enemy casualties!"
        
        return jsonify({
            "success": True,
            "message": effect_msg,
            "grenades": resources["grenade"]
        })
    
    return jsonify({
        "success": False,
        "message": "Cannot use that item right now."
    })

@app.route("/check_combat_status")
def check_combat_status():
    """Check if combat is pending for the frontend."""
    return jsonify({
        "combat_pending": session.get("combat_pending", False)
    })

@app.route("/get_combat_stats")
def get_combat_stats():
    """Provide combat stats for the enhanced combat system."""
    player = session.get("player", {})
    resources = session.get("resources", {})
    mission = session.get("mission", {})
    
    # Generate or get existing squad
    squad = session.get("squad", [])
    if not squad:
        from game_logic import generate_squad_members
        squad = generate_squad_members(player)
        session["squad"] = squad
    
    # Generate combat scenario
    from game_logic import generate_combat_scenario
    scenario = generate_combat_scenario(player, mission)
    
    return jsonify({
        "health": player.get("health", 100),
        "max_health": player.get("max_health", 100),
        "ammo": resources.get("ammo", 30),
        "grenades": resources.get("grenade", 2),
        "medkits": resources.get("medkit", 2),
        "squad": squad,
        "difficulty": mission.get("difficulty", "Medium"),
        "mission_type": mission.get("name", "patrol"),
        "scenario": scenario,
        "player_class": player.get("class", "Rifleman"),
        "player_weapon": player.get("weapon", "Rifle"),
        "player_rank": player.get("rank", "Private")
    })

@app.route("/integrate_combat_result", methods=["POST"])
def integrate_combat_result():
    """Integrate combat results into the story."""
    data = request.get_json() or {}
    outcome = data.get("outcome", "unknown")
    
    # Update player stats with safe data access
    player = session.get("player", {})
    if data:
        player["health"] = data.get("playerHealth", player.get("health", 100))
    
    # Update resources with safe data access
    resources = session.get("resources", {})
    if data:
        resources["ammo"] = data.get("playerAmmo", resources.get("ammo", 12))
        resources["grenade"] = data.get("playerGrenades", resources.get("grenade", 2))
        resources["medkit"] = data.get("playerMedkits", resources.get("medkit", 2))
    
    # Update player stats for combat resolution
    if outcome == "victory":
        session["battles_won"] = session.get("battles_won", 0) + 1
        player_stats = session.get("player_stats", initialize_player_stats())
        session["player_stats"] = update_player_stats(player_stats, "combat_victory")
    
    # Handle squad casualties with safe data access
    squad_casualties = data.get("squadCasualties", []) if data else []
    squad = session.get("squad", [])
    for casualty_name in squad_casualties:
        # Find and remove squad member by name
        for i, member in enumerate(squad):
            if member.get("name") == casualty_name:
                # Store dead member for potential revival later
                dead_members = session.get("dead_squad_members", [])
                dead_members.append(member)
                session["dead_squad_members"] = dead_members
                # Remove from active squad
                squad.pop(i)
                break
    
    # Generate combat story summary with safe data access
    enemies_eliminated = data.get("enemiesEliminated", 0) if data else 0
    total_enemies = data.get("totalEnemies", 1) if data else 1
    rounds = data.get("rounds", 1) if data else 1
    environment = data.get("environment", "open field") if data else "open field"
    
    # Create combat narrative to integrate into story
    combat_narrative = ""
    if outcome == "victory":
        combat_narrative = f"\n\n[COMBAT RESOLVED: After {rounds} rounds of intense fighting in the {environment}, you emerged victorious! {enemies_eliminated} of {total_enemies} enemies eliminated."
        if squad_casualties:
            combat_narrative += f" Casualties: {', '.join(squad_casualties)}."
        combat_narrative += " Your squad regroups and continues the mission.]"
        
        # Update battle stats
        session["battles_won"] = session.get("battles_won", 0) + 1
        player_stats = session.get("player_stats", initialize_player_stats())
        session["player_stats"] = update_player_stats(player_stats, "combat_victory")
        
    elif outcome == "retreat":
        combat_narrative = f"\n\n[TACTICAL RETREAT: After {rounds} rounds of combat, you successfully withdrew from the engagement. The squad falls back to regroup and reassess the situation.]"
        
    elif outcome == "defeat":
        combat_narrative = f"\n\n[COMBAT DEFEAT: Overwhelmed after {rounds} rounds of fighting, you were forced to abandon the mission. Critical wounds require immediate evacuation.]"
        player["health"] = 0
    
    # Append combat narrative to current story
    current_story = session.get("story", "")
    session["story"] = current_story + combat_narrative
    
    # Save updated state
    session["player"] = player
    session["resources"] = resources
    session["squad"] = squad
    
    # Clear combat pending flag and use stored story content
    session.pop("combat_pending", None)
    stored_story = session.pop("combat_story_content", "")
    
    # After combat, generate new story content with choices
    mission = session.get("mission", {})
    player = session.get("player", {})
    turn_count = session.get("turn_count", 0) + 1
    
    # Create post-combat story continuation 
    if stored_story:
        post_combat_story = stored_story + combat_narrative
    else:
        post_combat_story = combat_narrative
    
    # Generate tactical choices based on combat outcome and current situation
    if outcome == "victory":
        post_combat_choices = [
            "Continue advancing toward the objective.",
            "Secure the area and tend to wounded.",
            "Search for enemy intelligence or supplies."
        ]
    elif outcome == "retreat":
        post_combat_choices = [
            "Find alternative route to objective.",
            "Regroup and call for reinforcements.",
            "Assess casualties and plan next move."
        ]
    else:  # defeat
        post_combat_choices = [
            "Attempt emergency evacuation.",
            "Send distress signal to command.",
            "Find cover and wait for rescue."
        ]
    
    # Add choices to the story content
    choices_text = f"\n\n1. {post_combat_choices[0]}\n2. {post_combat_choices[1]}\n3. {post_combat_choices[2]}"
    full_story_with_choices = post_combat_story + choices_text
    
    # Update story and turn count
    session["story"] = current_story + combat_narrative + choices_text
    session["new_content"] = f"\n\n> Combat Resolution:\n\n{full_story_with_choices}"
    session["turn_count"] = turn_count
    
    # Save to database
    save_to_database()
    
    return jsonify({
        "success": True,
        "message": f"Combat {outcome}!",
        "story_continuation": full_story_with_choices,
        "redirect_to_play": True  # Signal frontend to continue story
    })

@app.route("/camp")
def camp():
    """Display camping/rest interface between missions."""
    player = session.get("player", {})
    resources = session.get("resources", {})
    squad = session.get("squad", [])
    
    # Check if player can camp (between missions)
    if not session.get("can_camp", False):
        return redirect(url_for("missions"))
    
    return render_template("camp.html",
                         player=player,
                         resources=resources,
                         squad=squad,
                         missions_completed=session.get("missions_completed", 0))

@app.route("/camp_action", methods=["POST"])
def camp_action():
    """Handle camping actions like rest, heal, resupply."""
    action = request.form.get("action")
    player = session.get("player", {})
    resources = session.get("resources", {})
    
    result_message = ""
    
    if action == "rest":
        # Rest restores health and morale
        heal_amount = random.randint(20, 40)
        morale_boost = random.randint(15, 25)
        
        player["health"] = min(100, player.get("health", 100) + heal_amount)
        player["morale"] = min(100, player.get("morale", 100) + morale_boost)
        
        result_message = f"You rest and recover. +{heal_amount} health, +{morale_boost} morale."
        
    elif action == "heal_squad":
        # Heal wounded squad members (medic bonus)
        squad = session.get("squad", [])
        healed = 0
        
        if player.get("class") == "Medic":
            # Medics can restore lost squad members
            dead_members = session.get("dead_squad_members", [])
            if dead_members and resources.get("medkit", 0) > 0:
                restored = dead_members.pop()
                squad.append(restored)
                resources["medkit"] -= 1
                healed += 1
                result_message = f"Your medical expertise saves {restored}! Squad member restored."
        else:
            result_message = "Squad is in good condition."
        
        session["squad"] = squad
        
    elif action == "resupply":
        # Resupply ammunition and equipment
        supply_found = random.random() < 0.7
        
        if supply_found:
            ammo_found = random.randint(5, 15)
            grenades_found = random.randint(0, 2)
            medkits_found = random.randint(0, 2)
            
            resources["ammo"] = min(30, resources.get("ammo", 12) + ammo_found)
            resources["grenade"] = min(5, resources.get("grenade", 2) + grenades_found)
            resources["medkit"] = min(5, resources.get("medkit", 2) + medkits_found)
            
            result_message = f"Supply cache found! +{ammo_found} ammo"
            if grenades_found > 0:
                result_message += f", +{grenades_found} grenades"
            if medkits_found > 0:
                result_message += f", +{medkits_found} medkits"
        else:
            result_message = "No supplies found in the area."
    
    elif action == "train":
        # Training improves combat effectiveness
        player["experience"] = player.get("experience", 0) + random.randint(10, 20)
        
        # Small chance to improve max health
        if random.random() < 0.3:
            player["max_health"] = min(120, player.get("max_health", 100) + 5)
            result_message = "Intensive training complete! Max health increased."
        else:
            result_message = "Training session complete. Combat skills improved."
    
    # Save state
    session["player"] = player
    session["resources"] = resources
    session["can_camp"] = False  # Can only camp once between missions
    
    save_to_database()
    
    return jsonify({
        "success": True,
        "message": result_message,
        "player": player,
        "resources": resources
    })

@app.route("/quick_save", methods=["POST"])
def quick_save():
    """Save current game state."""
    save_data = {
        "player": session.get("player", {}),
        "resources": session.get("resources", {}),
        "mission": session.get("mission", {}),
        "story": session.get("story", ""),
        "turn_count": session.get("turn_count", 0),
        "mission_phase": session.get("mission_phase", "start"),
        "score": session.get("score", 0),
        "save_timestamp": "Current mission state"
    }
    
    session["quick_save"] = save_data
    return jsonify({"success": True, "message": "Game progress saved!"})

@app.route("/quick_load", methods=["POST"])  
def quick_load():
    """Load saved game state."""
    save_data = session.get("quick_save")
    if save_data:
        for key, value in save_data.items():
            if key != "save_timestamp":
                session[key] = value
        
        return jsonify({
            "success": True, 
            "message": "Save loaded! Returning to saved position.",
            "redirect": url_for("play")
        })
    
    return jsonify({"success": False, "message": "No saved game found."})

@app.route("/reset")
def reset_game():
    """Reset the game session."""
    session.clear()
    return redirect(url_for("index"))

def save_to_database():
    """Save current session data to database."""
    from game_logic import get_session_id
    session_id = get_session_id()
    
    # Save player data
    player_data = session.get("player", {})
    resources = session.get("resources", {})
    if player_data:
        db.save_player_data(session_id, player_data, resources)
    
    # Save game session
    mission_data = session.get("mission", {})
    story_data = {
        "story": session.get("story", ""),
        "base_story": session.get("base_story", ""),
        "new_content": session.get("new_content", ""),
        "mission_phase": session.get("mission_phase", "start")
    }
    turn_count = session.get("turn_count", 0)
    score = session.get("score", 0)
    completed_missions = session.get("completed", [])
    player_stats = session.get("player_stats", {})
    
    db.save_game_session(session_id, mission_data, story_data, 
                        turn_count, score, completed_missions, player_stats)

def load_from_database():
    """Load session data from database."""
    from game_logic import get_session_id
    session_id = get_session_id()
    
    # Load player data
    player_data = db.load_player_data(session_id)
    if player_data:
        session["player"], session["resources"] = player_data
    
    # Load game session
    game_data = db.load_game_session(session_id)
    if game_data:
        if game_data['mission_data']:
            session["mission"] = game_data['mission_data']
        session.update(game_data['story_data'])
        session["turn_count"] = game_data['turn_count']
        session["score"] = game_data['score']
        session["completed"] = game_data['completed_missions']
        session["player_stats"] = game_data['player_stats']

def cleanup_session():
    """Clean up session data to prevent cookie overflow."""
    # Now we only keep minimal data in session, rest in database
    save_to_database()
    
    # Keep only essential session data
    essential_keys = ['game_session_id', 'player', 'resources', 'mission', 'story']
    session_copy = {k: v for k, v in session.items() if k in essential_keys}
    session.clear()
    session.update(session_copy)

# Removed duplicate route - using the enhanced version above

@app.route("/combat_result", methods=["POST"])
def combat_result():
    """Process combat results and update player state."""
    try:
        data = request.get_json()
        outcome = data.get("outcome")
        player_health = max(0, data.get("playerHealth", 100))
        player_ammo = max(0, data.get("playerAmmo", 12))
        player_grenades = max(0, data.get("playerGrenades", 2))
        rounds = data.get("rounds", 1)
        
        # Update player stats
        player = session.get("player", {})
        player["health"] = player_health
        session["player"] = player
        
        # Update resources
        resources = session.get("resources", {})
        resources["ammo"] = player_ammo
        resources["grenade"] = player_grenades
        session["resources"] = resources
        
        # Update player stats for achievements
        player_stats = session.get("player_stats", initialize_player_stats())
        
        if outcome == "victory":
            session["score"] = session.get("score", 0) + (50 * rounds)
            session["battles_won"] = session.get("battles_won", 0) + 1
            player_stats = update_player_stats(player_stats, "combat_victory")
            message = "Combat victorious! Enemy defeated."
            
            # Bonus rewards for good performance
            if player_health > 50:
                resources["medkit"] = resources.get("medkit", 0) + 1
                message += " Medical supplies recovered!"
                
        elif outcome == "retreat":
            message = "Successfully retreated from combat."
            player_stats = update_player_stats(player_stats, "combat_retreat")
            
        elif outcome == "defeat":
            message = "Critically wounded in combat. Mission compromised."
            player_stats = update_player_stats(player_stats, "combat_defeat")
            player["health"] = max(10, player_health)
            session["player"] = player
            
        else:
            message = "Combat resolved."
        
        session["player_stats"] = player_stats
        session["resources"] = resources
        
        return jsonify({"success": True, "message": message})
        
    except Exception as e:
        logging.error(f"Combat result error: {e}")
        return jsonify({"success": False, "message": "Combat resolution failed"})



@app.route("/reset")
def reset():
    """Reset game session."""
    # Preserve achievement stats across resets
    player_stats = session.get("player_stats", initialize_player_stats())
    session.clear()
    session["player_stats"] = player_stats
    return redirect(url_for("index"))

@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", error="Page not found"), 404

@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", error="Internal server error"), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



# ----------------------------
# AI HELPER ROUTES
# ----------------------------
from ai_editor import plan_changes, apply_changes, try_git_commit

@app.route("/admin/ai", methods=["GET"])
def ai_console():
    return render_template("ai_console.html")

@app.route("/admin/ai/plan", methods=["POST"])
def ai_plan():
    data = request.get_json(force=True)
    instruction = data.get("instruction", "").strip()
    if not instruction:
        return jsonify({"error": "Missing 'instruction'"}), 400
    try:
        plan = plan_changes(instruction)
        preview = [c["path"] for c in plan.get("changes", [])]
        return jsonify({"plan": plan, "preview": preview})

    except Exception as e:

        
        return jsonify({"error": str(e)}), 500

@app.route("/admin/ai/apply", methods=["POST"])
def ai_apply():
    plan = request.get_json(force=True)
    if not isinstance(plan, dict) or "changes" not in plan:
        return jsonify({"error": "Expected plan JSON with 'changes'"}), 400
    result = apply_changes(plan)
    try_git_commit(result["commit_message"])
    return jsonify({"result": result})



# ----------------------------
# Campaign helper functions and routes
# ----------------------------

from flask import session  # ensure session imported (already imported)

def get_campaign():
    if "campaign" not in session:
        session["campaign"] = {"missions": [], "current_index": -1, "killed_squad": [], "summary": ""}
    return session["campaign"]


def start_dday_if_needed():
    camp = get_campaign()
    if camp["current_index"] == -1:
        dday = {
            "code": "d_day",
            "name": "Operation Neptune (D-Day)",
            "difficulty": "Hard",
            "desc": "Land on Omaha Beach, breach the defenses, and secure exits for the push inland."
        }
        camp["missions"] = [dday]
        session["campaign"] = camp


def generate_next_mission_from_ai():
    camp = get_campaign()
    roster = session.get("squad", [])
    summary = camp.get("summary", "")
    try:
        import json
        from ai_editor import client
        prompt = f"""You are an AI DM generating the next WW2 mission for a text adventure.
Context summary: {summary}
Current squad: {', '.join(roster) if roster else 'none'}.
Return a JSON object with keys code, name, difficulty, desc for the next mission, and no extra commentary."""
        resp = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            input=[{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": prompt}]
        )
        text = resp.output_text.strip()
        start = text.find("{")
        end = text.rfind("}")
        mission = json.loads(text[start:end+1])
        for key in ("code", "name", "difficulty", "desc"):
            mission.setdefault(key, f"UNKNOWN_{key}")
        return mission
    except Exception:
        return {
            "code": "next_op",
            "name": "Next Operation",
            "difficulty": "Medium",
            "desc": "Proceed inland and secure a strategic village."
        }


@app.route("/campaign")
def campaign_menu():
    start_dday_if_needed()
    camp = get_campaign()
    player = session.get("player", {})
    score = session.get("score", 0)
    achievements_count = len(session.get("player_stats", {}).get("achievements_unlocked", []))
    return render_template("missions.html", missions=camp["missions"], player=player, score=score, achievements_count=achievements_count)


@app.route("/campaign/next")
def campaign_next():
    mission = generate_next_mission_from_ai()
    camp = get_campaign()
    camp["missions"].append(mission)
    camp["current_index"] = len(camp["missions"]) - 1
    session["campaign"] = camp
    return redirect(url_for("campaign_menu"))
