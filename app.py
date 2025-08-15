import os
import random
import re
import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
from achievements import (
    check_achievements, get_achievement_display, initialize_player_stats, 
    update_player_stats, ACHIEVEMENTS, HISTORICAL_TRIVIA
)

# Configure logging for better debugging
logging.basicConfig(level=logging.DEBUG)
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    logging.warning("OpenAI package not installed. AI features will be disabled.")

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.permanent_session_lifetime = 86400  # 24 hours
app.config['SESSION_PERMANENT'] = True

# Initialize OpenAI client
client = None
if OPENAI_API_KEY and OpenAI is not None:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logging.info("OpenAI client initialized successfully")
    except Exception as e:
        logging.error(f"OpenAI initialization error: {e}")
else:
    logging.warning("OpenAI API key not found or OpenAI not installed")

# Game configuration data
RANKS = ["Private", "Corporal", "Sergeant", "Lieutenant", "Captain"]
CLASSES = ["Rifleman", "Medic", "Gunner", "Sniper", "Demolitions"]
WEAPONS = ["Rifle", "SMG", "LMG", "Sniper Rifle", "Shotgun"]

MISSIONS = [
    {"name": "Sabotage the Bridge", "desc": "Destroy the enemy bridge to cut off reinforcements.", "difficulty": "Medium"},
    {"name": "Rescue POWs", "desc": "Free prisoners from a heavily guarded camp.", "difficulty": "Hard"},
    {"name": "Hold the Village", "desc": "Defend the village from waves of enemies.", "difficulty": "Easy"},
    {"name": "Intel Extraction", "desc": "Infiltrate enemy HQ and steal classified documents.", "difficulty": "Hard"},
    {"name": "Supply Drop", "desc": "Secure and defend a vital supply drop zone.", "difficulty": "Medium"},
    {"name": "Radio Tower", "desc": "Capture and hold the enemy communications tower.", "difficulty": "Easy"}
]

# Combat keywords for detecting battle scenarios
SURPRISE_COMBAT_KEYWORDS = [
    "combat", "ambush", "ambushed", "attack begins", "sudden attack", "under fire",
    "opens fire", "open fire", "firefight", "enemy fires", "battle erupts",
    "exchange of gunfire", "hostilities commence", "start shooting", "start firing",
    "enemy spotted", "take cover", "incoming fire", "gunshots ring out"
]

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

def resolve_combat_encounter(player: dict, chosen_action: str, mission: dict) -> dict:
    """Resolve combat encounters with detailed outcomes."""
    player_class = player.get("class", "Rifleman")
    difficulty = mission.get("difficulty", "Medium")
    
    # Base combat stats
    base_success_chance = 0.6
    base_damage = 15
    
    # Class bonuses
    class_modifiers = {
        "Gunner": {"success": 0.8, "damage_reduction": 0.7, "ammo_cost": 2},
        "Sniper": {"success": 0.9, "damage_reduction": 0.5, "ammo_cost": 1},
        "Rifleman": {"success": 0.7, "damage_reduction": 0.8, "ammo_cost": 1},
        "Medic": {"success": 0.5, "damage_reduction": 0.9, "ammo_cost": 1},
        "Demolitions": {"success": 0.6, "damage_reduction": 0.6, "ammo_cost": 3}
    }
    
    modifier = class_modifiers.get(player_class, class_modifiers["Rifleman"])
    
    # Difficulty adjustments
    difficulty_mods = {"Easy": 0.2, "Medium": 0.0, "Hard": -0.2}
    success_chance = base_success_chance + difficulty_mods.get(difficulty, 0.0) + (modifier["success"] - 0.6)
    
    # Action-based modifiers
    action_lower = chosen_action.lower()
    if "stealth" in action_lower or "sneak" in action_lower:
        success_chance += 0.2
    elif "charge" in action_lower or "assault" in action_lower:
        success_chance -= 0.1
        base_damage += 5
    
    victory = random.random() < success_chance
    damage_taken = 0 if victory else int(base_damage * modifier["damage_reduction"])
    
    if victory:
        descriptions = [
            f"Your {player_class.lower()} training pays off - enemy neutralized!",
            "Superior tactics lead to a decisive victory!",
            "Enemy forces are quickly overwhelmed by your assault!"
        ]
    else:
        descriptions = [
            f"The enemy puts up fierce resistance! You take {damage_taken} damage.",
            f"Combat is brutal - you're wounded but fighting continues! -{damage_taken} health.",
            f"Enemy fire finds its mark! You suffer {damage_taken} damage but press on."
        ]
    
    return {
        "victory": victory,
        "damage": damage_taken,
        "ammo_used": modifier["ammo_cost"],
        "description": random.choice(descriptions)
    }
        
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
    
    # Squad events (late in mission)
    if turn_count > 3 and random.random() < 0.2:
        squad_events = [
            "One of your squad members spots enemy movement.",
            "Your squad provides covering fire.",
            "A squad member reports radio chatter."
        ]
        events.append(random.choice(squad_events))
    
    return " ".join(events) if events else ""

@app.route("/")
def index():
    """Character creation and game start page."""
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
    """Display available missions."""
    completed = set(session.get("completed", []))
    available = [m for m in MISSIONS if m["name"] not in completed]
    
    # Campaign progression system
    missions_completed_count = len(completed)
    
    if not available:
        # Unlock advanced campaign missions
        advanced_missions = [
            {"name": "Operation Overlord", "desc": "Lead the D-Day assault on Normandy beach.", "difficulty": "Extreme"},
            {"name": "Battle of the Bulge", "desc": "Hold the line against the German counteroffensive.", "difficulty": "Extreme"},
            {"name": "Liberation of Paris", "desc": "Spearhead the liberation of the French capital.", "difficulty": "Hard"}
        ]
        available = MISSIONS + advanced_missions
    else:
        # Lock advanced missions until player completes basic ones
        if missions_completed_count < 3:
            available = [m for m in available if m.get("difficulty") != "Extreme"]
    
    # Get achievements count for template
    player_stats = session.get("player_stats", {})
    achievements_count = len(player_stats.get("achievements_unlocked", []))
    
    return render_template("missions.html", 
                         missions=available, 
                         player=session.get("player"),
                         score=session.get("score", 0),
                         achievements_count=achievements_count)

@app.route("/start_mission", methods=["POST"])
def start_mission():
    """Initialize selected mission."""
    chosen_mission = request.form.get("mission")
    mission = next((m for m in MISSIONS if m["name"] == chosen_mission), MISSIONS[0])
    session["mission"] = mission
    
    # Initialize turn tracking and story progression
    session["turn_count"] = 0
    session["story_history"] = []
    session["mission_phase"] = "start"  # start, middle, climax, end
    
    # Mission briefing reward
    resources = session.get("resources", {})
    resources["ammo"] = resources.get("ammo", 0) + 3
    session["resources"] = resources
    
    player = session.get("player", {})
    squad = session.get("squad", [])
    
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
    
    story = ai_chat(system_msg, user_prompt)
    
    # Initialize clean session for new mission
    session["story"] = story
    session["base_story"] = ""  # Reset base story
    session["new_content"] = ""  # Reset new content
    session["turn_count"] = 0  # Reset turn counter
    session["story_history"] = [{"turn": 0, "content": story, "type": "start"}]  # Fresh history
    
    logging.info(f"Mission started: {mission['name']}")
    return redirect(url_for("play"))

@app.route("/play")
def play():
    """Main gameplay interface."""
    story = session.get("story", "")
    if not story:
        return redirect(url_for("mission_menu"))
    
    choices = parse_choices(story)
    
    # Progressive story display: separate base story from new content
    base_story = session.get("base_story", "")
    new_content = session.get("new_content", "")
    turn_count = session.get("turn_count", 0)
    
    return render_template("play.html", 
                         story=story,
                         base_story=base_story,
                         new_content=new_content,
                         choices=choices,
                         player=session.get("player", {}), 
                         resources=session.get("resources", {}),
                         mission=session.get("mission", {}),
                         turn_count=turn_count,
                         squad=session.get("squad", []))

@app.route("/make_choice", methods=["POST"])
@app.route("/choose", methods=["POST"])
def make_choice():
    """Process player's choice and continue story."""
    try:
        choice_index = int(request.form.get("choice", "1")) - 1
        
        # Get current story and parse fresh choices
        current_story = session.get("story", "")
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
        session["player_stats"] = update_player_stats(session["player_stats"], "choice_made")
        
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
        
        # Check for success indicators in AI response
        if any(keyword in new_content.lower() for keyword in success_keywords):
            return complete_mission(story + f"\n\nMISSION OBJECTIVE ACHIEVED: {chosen_action}")
        
        # Auto-complete after 6 turns to prevent infinite games
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
            session["player_stats"] = update_player_stats(session["player_stats"], "player_death")
            story += "\n--- MISSION FAILED ---\nYou have been critically wounded and the mission is aborted."
            session["story"] = story
            return redirect(url_for("base_camp"))
        
        # Enhanced story generation with context
        mission_phase = session.get("mission_phase", "middle")
        mission = session.get("mission", {})
        
        # Dynamic system message based on mission phase
        if mission_phase == "middle":
            phase_instruction = "Develop the mission further. Introduce challenges, obstacles, or tactical situations that test the player's decisions."
        elif mission_phase == "climax":
            phase_instruction = "Build toward the mission climax. Increase tension and make stakes higher. The objective should be within reach but challenging."
        else:  # end phase
            phase_instruction = "Move toward mission completion. Provide opportunities to complete the objective or create final dramatic moments."
        
        system_msg = (
            f"You are a WWII text adventure narrator. Continue the story based on the player's choice. "
            f"REQUIREMENTS: "
            f"1. Show immediate consequences of the player's choice: {chosen_action} "
            f"2. This is turn {turn_count} of mission: {mission.get('name')} "
            f"3. {phase_instruction} "
            f"4. ALWAYS end with exactly 3 numbered tactical choices like this: "
            f"1. [specific action] "
            f"2. [different action] "
            f"3. [alternative action] "
            f"5. Keep choices concrete and tactical, not vague. "
            f"6. Write 2-3 paragraphs then provide the 3 choices."
        )
        
        user_prompt = (
            f"Player chose: {chosen_action}\n"
            f"Mission: {mission.get('name')}\n"
            f"Player: {player.get('name')} ({player.get('class')}) - Health: {player.get('health', 100)}\n"
            f"Continue the story showing what happens after this choice."
        )
        
        new_content = ai_chat(system_msg, user_prompt)
        logging.info(f"Generated content: {new_content[:200]}...")
        
        # Parse choices from the new content immediately
        fresh_choices = parse_choices(new_content)
        logging.info(f"Parsed choices: {fresh_choices}")
        
        # If no valid choices found, add fallback choices to the content
        if len(fresh_choices) < 3:
            fallback_choices = generate_contextual_choices(player, mission, turn_count)
            choices_text = f"\n\n1. {fallback_choices[0]}\n2. {fallback_choices[1]}\n3. {fallback_choices[2]}"
            new_content += choices_text
            logging.info(f"Added fallback choices: {fallback_choices}")
        
        # Progressive story system: separate new content from base story
        choice_result = f"\n\n> You chose: {chosen_action}\n\n{new_content}"
        
        # Update story history for context
        story_history = session.get("story_history", [])
        story_history.append({
            "turn": turn_count,
            "choice": chosen_action,
            "content": new_content,
            "type": "continuation"
        })
        session["story_history"] = story_history
        
        # Progressive story system: only show new content typing
        session["new_content"] = choice_result
        
        # Update the full story for next iteration - this is critical for choice parsing
        new_full_story = base_story + choice_result
        session["story"] = new_full_story
        
        # Critical optimization: limit story history to prevent session bloat
        if len(story_history) > 6:
            session["story_history"] = story_history[-4:]  # Keep only last 4 turns
            
        # Also limit the base story size to prevent exponential growth
        if len(base_story) > 3000:  # About 3KB limit
            # Keep only the mission start and recent content
            story_lines = base_story.split('\n')
            if len(story_lines) > 50:
                session["base_story"] = '\n'.join(story_lines[:20] + story_lines[-20:])  # Keep start and recent
        
        # Enhanced combat system
        if any(keyword in new_content.lower() for keyword in SURPRISE_COMBAT_KEYWORDS):
            combat_result = resolve_combat_encounter(player, chosen_action, mission)
            if combat_result["victory"]:
                session["battles_won"] = session.get("battles_won", 0) + 1
                session["player_stats"] = update_player_stats(session["player_stats"], "combat_victory")
                story += f"\n\nCOMBAT RESULT: {combat_result['description']}"
            else:
                story += f"\n\nCOMBAT RESULT: {combat_result['description']}"
            
            # Apply combat consequences
            player["health"] = max(0, player.get("health", 100) - combat_result.get("damage", 0))
            resources["ammo"] = max(0, resources.get("ammo", 0) - combat_result.get("ammo_used", 1))
        
        # Auto-save game state
        session["player"] = player
        session["resources"] = resources
        session.permanent = True
        
        return redirect(url_for("play"))
        
    except Exception as e:
        logging.error(f"Error in make_choice: {e}")
        return render_template("error.html", error=str(e))

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
            session["player_stats"] = update_player_stats(session["player_stats"], "item_used")
            
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
