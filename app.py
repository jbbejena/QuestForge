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
    """Extract numbered choices from AI-generated text."""
    lines = text.splitlines()
    choices = []
    
    for line in lines:
        # Match patterns like "1. Choice text" or "1) Choice text"
        match = re.match(r"\s*([1-3])[\.\)]\s*(.+)", line)
        if match:
            choices.append(match.group(2).strip())
    
    # Ensure we always have exactly 3 choices
    while len(choices) < 3:
        choices.append("Continue forward.")
    
    return choices[:3]

def get_difficulty_modifier(difficulty: str) -> dict:
    """Get difficulty-based modifiers for missions."""
    modifiers = {
        "Easy": {"health_loss_min": 0, "health_loss_max": 10, "reward": 50},
        "Medium": {"health_loss_min": 5, "health_loss_max": 20, "reward": 100},
        "Hard": {"health_loss_min": 10, "health_loss_max": 30, "reward": 200}
    }
    return modifiers.get(difficulty, modifiers["Medium"])

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
    session["story"] = story
    session["story_history"].append({"turn": 0, "content": story, "type": "start"})
    
    logging.info(f"Mission started: {mission['name']}")
    return redirect(url_for("play"))

@app.route("/play")
def play():
    """Main gameplay interface."""
    story = session.get("story", "")
    if not story:
        return redirect(url_for("mission_menu"))
    
    choices = parse_choices(story)
    
    return render_template("play.html", 
                         story=story, 
                         choices=choices,
                         player=session.get("player", {}), 
                         resources=session.get("resources", {}),
                         mission=session.get("mission", {}))

@app.route("/make_choice", methods=["POST"])
@app.route("/choose", methods=["POST"])
def make_choice():
    """Process player's choice and continue story."""
    try:
        choice_index = int(request.form.get("choice", "1")) - 1
        current_story = session.get("story", "")
        choices = parse_choices(current_story)
        
        if 0 <= choice_index < len(choices):
            chosen_action = choices[choice_index]
        else:
            chosen_action = "Continue forward."
        
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
        
        # Update story with player's choice
        story = current_story + f"\n\n> You chose: {chosen_action}\n"
        
        # Check for mission completion keywords
        completion_keywords = ["return to base", "exfiltrate", "mission complete", "objective secured", "fall back"]
        if any(keyword in chosen_action.lower() for keyword in completion_keywords):
            return complete_mission(story)
        
        # Apply choice consequences
        player = session.get("player", {})
        resources = session.get("resources", {})
        mission = session.get("mission", {})
        
        # Random event consequences based on mission difficulty
        difficulty_mod = get_difficulty_modifier(mission.get("difficulty", "Medium"))
        
        if random.random() < 0.4:  # 40% chance of taking damage
            damage = random.randint(difficulty_mod["health_loss_min"], difficulty_mod["health_loss_max"])
            player["health"] = max(0, player.get("health", 100) - damage)
            if damage > 0:
                story += f"The action costs you {damage} health points.\n"
                # Update achievement stats for damage taken
                session["player_stats"] = update_player_stats(session["player_stats"], "damage_taken", damage=damage)
        else:
            # Chance to find resources or recover health
            if random.random() < 0.3:  # 30% chance
                heal = random.randint(5, 15)
                player["health"] = min(100, player.get("health", 100) + heal)
                story += f"You recover {heal} health points.\n"
        
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
            f"Continue this WWII text adventure story. You are turn {turn_count} of this mission. "
            f"Phase: {mission_phase}. {phase_instruction} "
            "IMPORTANT: Build directly on the player's choice - show immediate consequences and reactions. "
            "Always end with exactly 3 numbered tactical choices (format: 1. [action]). "
            "Make each choice feel distinct and meaningful. "
            "Keep responses focused and engaging (1-2 paragraphs plus choices). "
            "If the mission should end, include completion keywords like 'mission complete' or 'objective secured'."
        )
        
        # Get recent story context for better continuity
        story_history = session.get("story_history", [])
        recent_context = ""
        if len(story_history) > 0:
            recent_context = f"Previous context: {story_history[-1].get('content', '')[:200]}...\n\n"
        
        user_prompt = (
            f"Mission: {mission.get('name')} - {mission.get('desc')}\n"
            f"Turn {turn_count} | Phase: {mission_phase}\n"
            f"Player: {player.get('name')} ({player.get('rank')} {player.get('class')})\n"
            f"Health: {player.get('health', 100)}/100 | "
            f"Ammo: {resources.get('ammo', 0)} | Medkits: {resources.get('medkit', 0)} | Grenades: {resources.get('grenade', 0)}\n\n"
            f"{recent_context}"
            f"Player's choice: {chosen_action}\n\n"
            "Continue the story showing the consequences of this choice and provide 3 new tactical options."
        )
        
        new_content = ai_chat(system_msg, user_prompt)
        story += new_content
        
        # Save story progression to history
        story_history = session.get("story_history", [])
        story_history.append({
            "turn": turn_count,
            "choice": chosen_action,
            "content": new_content,
            "type": "continuation"
        })
        session["story_history"] = story_history
        
        # Check for combat and update stats
        if any(keyword in new_content.lower() for keyword in SURPRISE_COMBAT_KEYWORDS):
            if random.random() < 0.6:  # 60% chance to win combat
                session["battles_won"] = session.get("battles_won", 0) + 1
                session["player_stats"] = update_player_stats(session["player_stats"], "combat_victory")
        
        # Auto-save game state
        session["story"] = story
        session["player"] = player
        session["resources"] = resources
        session.permanent = True
        
        return redirect(url_for("play"))
        
    except Exception as e:
        logging.error(f"Error in make_choice: {e}")
        return render_template("error.html", error=str(e))

def complete_mission(story):
    """Handle mission completion."""
    mission = session.get("mission", {})
    difficulty_mod = get_difficulty_modifier(mission.get("difficulty", "Medium"))
    
    # Award score based on difficulty and health remaining
    base_score = difficulty_mod["reward"]
    health_bonus = session.get("player", {}).get("health", 0)
    total_score = base_score + health_bonus
    
    session["score"] = session.get("score", 0) + total_score
    session["missions_completed"] = session.get("missions_completed", 0) + 1
    
    # Add to completed missions
    completed = session.get("completed", [])
    if mission.get("name") not in completed:
        completed.append(mission["name"])
        session["completed"] = completed
    
    # Update achievement stats
    session["player_stats"] = update_player_stats(
        session["player_stats"], 
        "mission_completed", 
        score=total_score
    )
    
    # Check for new achievements
    new_achievements = check_achievements(session["player_stats"])
    if new_achievements:
        # Mark achievements as unlocked
        unlocked = session["player_stats"].get("achievements_unlocked", [])
        for achievement_id in new_achievements:
            if achievement_id not in unlocked:
                unlocked.append(achievement_id)
        session["player_stats"]["achievements_unlocked"] = unlocked
        
        # Store new achievements for display
        session["new_achievements"] = [get_achievement_display(aid) for aid in new_achievements]
    
    story += f"\n\n--- MISSION COMPLETE ---\nScore earned: {total_score} points"
    session["story"] = story
    
    return redirect(url_for("base_camp"))

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
