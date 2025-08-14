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
    lines = text.splitlines()
    choices = []
    
    for line in lines:
        # Match patterns like "1. Choice text" or "1) Choice text" or "1 - Choice text"
        match = re.match(r"\s*([1-3])[\.\)\-\s]+(.+)", line.strip())
        if match and len(match.group(2).strip()) > 0:
            choice_text = match.group(2).strip()
            # Remove any markdown or HTML tags
            choice_text = re.sub(r'<[^>]+>', '', choice_text)
            choice_text = re.sub(r'\*\*([^\*]*)\*\*', r'\1', choice_text)  # Remove bold
            choices.append(choice_text)
    
    # Fallback choices if parsing fails or insufficient choices found
    fallback_choices = [
        "Advance cautiously forward.",
        "Take defensive position and observe.",
        "Retreat to a safer location."
    ]
    
    # Ensure we always have exactly 3 choices
    while len(choices) < 3:
        fallback_index = len(choices)
        if fallback_index < len(fallback_choices):
            choices.append(fallback_choices[fallback_index])
        else:
            choices.append("Continue with the mission.")
    
    return choices[:3]

def get_difficulty_modifier(difficulty: str) -> dict:
    """Get difficulty-based modifiers for missions."""
    modifiers = {
        "Easy": {"health_loss_min": 0, "health_loss_max": 10, "reward": 50, "event_chance": 0.3},
        "Medium": {"health_loss_min": 5, "health_loss_max": 20, "reward": 100, "event_chance": 0.4},
        "Hard": {"health_loss_min": 10, "health_loss_max": 30, "reward": 200, "event_chance": 0.5}
    }
    return modifiers.get(difficulty, modifiers["Medium"])

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
            player["morale"] = min(100, player.get("morale", 100) + 15)
        
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
    squad_members = [
        "Thompson (Rifleman)", "Garcia (Medic)", "Kowalski (Gunner)",
        "Anderson (Sniper)", "Martinez (Demo)", "Chen (Scout)",
        "O'Brien (Engineer)", "Williams (Radio)", "Jackson (Veteran)"
    ]
    squad_size = random.randint(3, 5)
    session["squad"] = random.sample(squad_members, squad_size)
    
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
    
    # If all missions completed, allow replay
    if not available:
        available = MISSIONS
    
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
    print(f"DEBUG: Displaying choices on play page: {choices}")
    
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
        print(f"DEBUG: Current story length: {len(current_story)}")
        print(f"DEBUG: Story ending: ...{current_story[-200:] if len(current_story) > 200 else current_story}")
        
        # Debug logging for choice selection
        raw_choice = request.form.get("choice", "1")
        print(f"DEBUG: Raw choice from form: '{raw_choice}'")
        print(f"DEBUG: Choice index calculated: {choice_index}")
        print(f"DEBUG: Available choices: {choices}")
        
        if 0 <= choice_index < len(choices):
            chosen_action = choices[choice_index]
        else:
            print(f"DEBUG: Invalid choice index {choice_index}, using fallback")
            chosen_action = choices[0] if choices else "Continue forward."
            
        print(f"DEBUG: FINAL SELECTED ACTION: '{chosen_action}'")
        
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
        
        # Check for mission completion keywords
        completion_keywords = ["return to base", "exfiltrate", "mission complete", "objective secured", "fall back"]
        if any(keyword in chosen_action.lower() for keyword in completion_keywords):
            return complete_mission(story)
        
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
            f"You are a WWII text adventure narrator maintaining strict story continuity. "
            f"CRITICAL: Continue the EXACT existing storyline - NEVER restart or reset the scenario. "
            f"This is turn {turn_count} of an ongoing mission in progress. "
            f"Mission phase: {mission_phase}. {phase_instruction} "
            f"Build directly upon the player's previous choice with immediate consequences. "
            f"End with exactly 3 numbered tactical choices advancing THIS storyline. "
            f"Format: 1. [action] 2. [action] 3. [action]"
        )
        
        # Build comprehensive story context to prevent AI confusion
        story_history = session.get("story_history", [])
        
        # Create a concise but complete context from recent story progression
        context_summary = ""
        recent_story_progression = ""
        
        # Use the last 2-3 turns for immediate context
        if len(story_history) > 1:
            recent_turns = story_history[-2:]  # Focus on most recent context
            for turn in recent_turns:
                if turn.get("choice") and turn.get("content"):
                    context_summary += f"Previous: '{turn['choice']}' resulted in: {turn['content'][:100]}...\n"
                    recent_story_progression += f"> {turn['choice']}\n{turn['content']}\n\n"
        
        user_prompt = (
            f"MISSION: {mission.get('name')} (Turn {turn_count})\n"
            f"PLAYER: {player.get('name')} - {player.get('class')} with {player.get('health', 100)} health\n"
            f"PHASE: {mission_phase}\n\n"
            f"RECENT STORY:\n{recent_story_progression}"
            f"CURRENT CHOICE: {chosen_action}\n\n"
            f"Show the immediate results of this choice. Continue this exact storyline."
        )
        
        new_content = ai_chat(system_msg, user_prompt)
        print(f"DEBUG: AI Response: {new_content[:200]}...")
        
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
        
        # Verify choices are properly extracted from new content
        updated_choices = parse_choices(new_full_story)
        print(f"DEBUG: Updated choices after AI response: {updated_choices}")
        
        # Critical optimization: limit story history to prevent session bloat
        if len(story_history) > 6:
            session["story_history"] = story_history[-4:]  # Keep only last 4 turns
            
        # Also limit the base story size to prevent exponential growth
        if len(base_story) > 3000:  # About 3KB limit
            # Keep only the mission start and recent content
            story_lines = base_story.split('\n')
            if len(story_lines) > 50:
                session["base_story"] = '\n'.join(story_lines[:20] + story_lines[-20:])  # Keep start and recent
        
        # Check for combat and update stats
        if any(keyword in new_content.lower() for keyword in SURPRISE_COMBAT_KEYWORDS):
            if random.random() < 0.6:  # 60% chance to win combat
                session["battles_won"] = session.get("battles_won", 0) + 1
                session["player_stats"] = update_player_stats(session["player_stats"], "combat_victory")
        
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
    health_bonus = player.get("health", 0)
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
    if new_achievements:
        unlocked = session["player_stats"].get("achievements_unlocked", [])
        for achievement_id in new_achievements:
            if achievement_id not in unlocked:
                unlocked.append(achievement_id)
        session["player_stats"]["achievements_unlocked"] = unlocked
        session["new_achievements"] = [get_achievement_display(aid) for aid in new_achievements]
    
    # Generate dynamic mission completion text
    completion_text = generate_mission_completion_text(mission_outcome, total_score)
    story += f"\n\n{completion_text}"
    session["story"] = story
    
    return redirect(url_for("base_camp"))

def calculate_mission_outcome(player: dict, resources: dict, turn_count: int, story_history: list, difficulty_mod: dict) -> dict:
    """Calculate mission outcome based on player performance."""
    outcome = {
        "rating": "Standard",
        "stealth_bonus": 0,
        "efficiency_bonus": 0,
        "special_notes": []
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
