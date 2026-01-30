import os
import random
import re
import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session
from dotenv import load_dotenv
from achievements import (
    check_achievements, get_achievement_display, initialize_player_stats, 
    update_player_stats, ACHIEVEMENTS, HISTORICAL_TRIVIA
)

# Configure logging
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

# --- SERVER-SIDE SESSION CONFIGURATION ---
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_FILE_DIR"] = "./flask_session"
app.config["SESSION_FILE_THRESHOLD"] = 500
Session(app)
# -----------------------------------------

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
# ... rest of your code stays exactly the same ...

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
        # Fallback content when AI is not available
        fallback_stories = [
            "The morning mist hangs heavy over the battlefield as you advance with your squad. Intelligence reports enemy movement ahead.\n\n1. Move forward cautiously through the trees.\n2. Send a scout to investigate the area.\n3. Set up defensive positions and wait.",
            "Your radio crackles with urgent messages from command. The situation is developing rapidly.\n\n1. Request immediate reinforcements.\n2. Advance to the objective as planned.\n3. Fall back to a safer position.",
            "The sound of distant artillery echoes across the valley. Your squad awaits your orders.\n\n1. Press forward to the objective.\n2. Take cover and assess the situation.\n3. Contact HQ for new instructions."
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

    # Create player character
    player_class = request.form.get("char_class", "Rifleman")
    session["player"] = {
        "name": request.form.get("name", "Rookie").strip() or "Rookie",
        "rank": request.form.get("rank", "Private"),
        "class": player_class,
        "weapon": request.form.get("weapon", "Rifle"),
        "health": 100,
        "max_health": 100
    }

    # Update achievement stats
    session["player_stats"] = update_player_stats(
        session["player_stats"], 
        "class_selected", 
        class_name=player_class
    )

    # Initialize resources
    session["resources"] = {
        "medkit": 2,
        "grenade": 2,
        "ammo": 12,
        "intel": 0
    }

    # Initialize squad
    session["squad"] = [
        "Smith (Medic)",
        "Johnson (Gunner)", 
        "Williams (Sniper)",
        "Brown (Demolitions)",
        "Jones (Rifleman)"
    ]

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

    # Mission briefing reward
    resources = session.get("resources", {})
    resources["ammo"] = resources.get("ammo", 0) + 3
    session["resources"] = resources

    player = session.get("player", {})
    squad = session.get("squad", [])

    # Generate initial mission scenario
    system_msg = (
        "You are a WWII text-adventure game master. "
        "Create an immersive opening scenario for the player's chosen mission. "
        "Write 2-3 paragraphs setting the scene, mentioning the player's rank, class, and weapon. "
        "Always end with exactly 3 numbered tactical choices (1, 2, 3). "
        "Make the scenario authentic to WWII combat operations. "
        "If combat is imminent, include the word 'combat' clearly in the text."
    )

    user_prompt = (
        f"Player: {player.get('name')} — {player.get('rank')} {player.get('class')} equipped with {player.get('weapon')}\n"
        f"Squad: {', '.join(squad)}\n"
        f"Mission: {mission['name']} — {mission['desc']}\n"
        f"Difficulty: {mission['difficulty']}\n"
        "Create the opening scenario with 3 numbered tactical choices."
    )

    story = ai_chat(system_msg, user_prompt)
    session["story"] = story

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

        logging.info(f"Player chose option {choice_index + 1}: {chosen_action}")
        logging.debug(f"Current story length: {len(current_story)} characters")
        logging.debug(f"Session keys: {list(session.keys())}")

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
                player["health"] = min(player.get("max_health", 100), player.get("health", 100) + heal)
                story += f"You recover {heal} health points.\n"

        session["player"] = player

        # Generate next scenario
        system_msg = (
            "You are a WWII text-adventure game master. "
            "Continue the story based on the player's previous choice. "
            "Write 1-2 paragraphs advancing the narrative. "
            "Always end with exactly 3 numbered tactical choices. "
            "Include a 'return to base' or 'complete mission' choice if the objective can be completed. "
            "If combat breaks out, clearly include the word 'combat' in the text."
        )

        # Create continuation prompt
        recent_story = '\n'.join(story.split('\n')[-20:])  # Keep last 20 lines for context
        prompt = f"Recent story context:\n{recent_story}\n\nPlayer Health: {player.get('health', 100)}/100"

        next_scenario = ai_chat(system_msg, prompt)
        story += "\n" + next_scenario

        # Check for combat and auto-resolve
        if any(keyword in next_scenario.lower() for keyword in SURPRISE_COMBAT_KEYWORDS):
            story = resolve_combat(story, player, resources)

        # Keep story manageable to prevent cookie overflow (FIX)
        story_parts = story.split('\n\n')
        if len(story_parts) > 20:  # Reduced from 15 to 5
            # Keep the mission briefing (first part) and recent parts
            story = story_parts[0] + '\n\n...[Earlier events]...\n\n' + '\n\n'.join(story_parts[-4:])

        session["story"] = story

        # Check for game over condition
        if player.get("health", 0) <= 0:
            # Update achievement stats for death
            session["player_stats"] = update_player_stats(session["player_stats"], "player_death")
            return redirect(url_for("game_over"))

        return redirect(url_for("play"))

    except Exception as e:
        logging.error(f"Error in make_choice: {e}")
        return render_template("error.html", error=f"Game error: {str(e)}"), 500

def resolve_combat(story: str, player: dict, resources: dict) -> str:
    """Auto-resolve combat encounters."""
    # Combat outcome based on player stats and random chance
    combat_skill = 0.7  # Base skill

    # Modify based on class
    if player.get("class") == "Sniper":
        combat_skill += 0.1
    elif player.get("class") == "Gunner":
        combat_skill += 0.1
    elif player.get("class") == "Demolitions":
        combat_skill += 0.05

    # Check if player has advantages
    if resources.get("ammo", 0) > 5:
        combat_skill += 0.1
    if resources.get("grenade", 0) > 0:
        combat_skill += 0.15
        resources["grenade"] -= 1  # Use grenade in combat

    # Determine outcome
    if random.random() < combat_skill:
        # Victory
        damage = random.randint(5, 15)
        player["health"] = max(1, player.get("health", 100) - damage)
        story += f"\n\n[COMBAT RESOLVED]\nYou and your squad emerge victorious! You sustained {damage} damage but eliminated the enemy threat.\n"

        # Combat rewards
        resources["ammo"] = resources.get("ammo", 0) + random.randint(2, 5)
        if random.random() < 0.3:
            resources["medkit"] = resources.get("medkit", 0) + 1
            story += "You found a medical kit among the enemy supplies.\n"

        session["battles_won"] = session.get("battles_won", 0) + 1
        session["score"] = session.get("score", 0) + 25

        # Update achievement stats for combat victory
        session["player_stats"] = update_player_stats(session["player_stats"], "combat_victory")
    else:
        # Defeat/Heavy casualties
        damage = random.randint(20, 40)
        player["health"] = max(0, player.get("health", 100) - damage)
        story += f"\n\n[COMBAT RESOLVED]\nThe enemy had the advantage. Your squad took heavy casualties and you suffered {damage} damage.\n"

        # Loss of resources
        resources["ammo"] = max(0, resources.get("ammo", 0) - random.randint(2, 4))

    # Use ammo in combat
    resources["ammo"] = max(0, resources.get("ammo", 0) - random.randint(1, 3))

    # Generate post-combat scenario
    system_msg = (
        "A combat encounter has just been resolved. "
        "Write a brief aftermath scenario with exactly 3 numbered choices. "
        "Include tactical options like treating wounded, securing the area, or advancing. "
        "Do not immediately start another combat."
    )

    prompt = f"{story}\n\nPlayer Health: {player.get('health', 100)}/100"
    aftermath = ai_chat(system_msg, prompt, temperature=0.6)
    story += "\n" + aftermath

    return story

def complete_mission(story: str):
    """Handle mission completion."""
    mission = session.get("mission", {})
    player = session.get("player", {})

    # Add mission to completed list
    completed = session.get("completed", [])
    if mission.get("name") and mission["name"] not in completed:
        completed.append(mission["name"])
        session["completed"] = completed

    # Calculate mission rewards
    difficulty_mod = get_difficulty_modifier(mission.get("difficulty", "Medium"))
    base_reward = difficulty_mod["reward"]

    # Bonus for health remaining
    health_bonus = max(0, (player.get("health", 0) - 50) * 2)
    total_reward = base_reward + health_bonus

    session["score"] = session.get("score", 0) + total_reward
    session["missions_completed"] = session.get("missions_completed", 0) + 1

    # Update achievement stats
    player_stats = session.get("player_stats", {})
    player_stats = update_player_stats(player_stats, "mission_completed", score=total_reward)

    # Check if mission was completed with squad
    if len(session.get("squad", [])) > 2:
        player_stats = update_player_stats(player_stats, "squad_mission_success")

    session["player_stats"] = player_stats

    # Check for new achievements
    new_achievements = check_achievements(player_stats)
    if new_achievements:
        # Add new achievements to unlocked list
        unlocked = player_stats.get("achievements_unlocked", [])
        for achievement_id in new_achievements:
            if achievement_id not in unlocked:
                unlocked.append(achievement_id)
        player_stats["achievements_unlocked"] = unlocked
        session["player_stats"] = player_stats

        # Store achievements for display
        session["new_achievements"] = new_achievements

    # Heal player after successful mission
    player["health"] = min(player.get("max_health", 100), player.get("health", 0) + 20)
    session["player"] = player

    logging.info(f"Mission completed: {mission.get('name')} - Score: {total_reward}")
    return redirect(url_for("base"))

@app.route("/base")
def base():
    """Base/headquarters screen showing progress."""
    return render_template("base.html",
                         completed=session.get("completed", []),
                         score=session.get("score", 0),
                         missions_completed=session.get("missions_completed", 0),
                         battles_won=session.get("battles_won", 0),
                         player=session.get("player", {}))

@app.route("/use_item", methods=["POST"])
def use_item():
    """Allow player to use items during gameplay."""
    item = request.form.get("item")
    resources = session.get("resources", {})
    player = session.get("player", {})

    if item == "medkit" and resources.get("medkit", 0) > 0:
        heal_amount = 30
        player["health"] = min(player.get("max_health", 100), player.get("health", 0) + heal_amount)
        resources["medkit"] -= 1

        # Update achievement stats for item usage
        session["player_stats"] = update_player_stats(session["player_stats"], "item_used")

        session["player"] = player
        session["resources"] = resources
        session.permanent = True  # Ensure session persists

        return jsonify({"success": True, "message": f"Used medkit. Restored {heal_amount} health.", "health": player["health"]})

    return jsonify({"success": False, "message": "Cannot use that item right now."})

@app.route("/stream_story")
def stream_story():
    """Stream story content for typewriter effect."""
    story = session.get("story", "")
    return jsonify({"story": story})

@app.route("/game_over")
def game_over():
    """Game over screen."""
    return render_template("game_over.html", 
                         player=session.get("player", {}),
                         score=session.get("score", 0),
                         missions_completed=session.get("missions_completed", 0))

@app.route("/achievements")
def achievements():
    """Display achievements and trivia."""
    player_stats = session.get("player_stats", initialize_player_stats())
    unlocked_achievements = player_stats.get("achievements_unlocked", [])

    # Get achievement display data
    achievements_data = []
    for achievement_id, achievement in ACHIEVEMENTS.items():
        display_data = dict(get_achievement_display(achievement_id))
        display_data["unlocked"] = achievement_id in unlocked_achievements
        achievements_data.append(display_data)

    # Check for new achievements and clear the flag
    new_achievements = session.pop("new_achievements", [])
    new_achievement_data = []
    for achievement_id in new_achievements:
        new_achievement_data.append(get_achievement_display(achievement_id))

    return render_template("achievements.html",
                         achievements=achievements_data,
                         new_achievements=new_achievement_data,
                         player_stats=player_stats)

@app.route("/reset")
def reset():
    """Reset game session."""
    # Preserve achievements across resets
    player_stats = session.get("player_stats", {})
    session.clear()
    if player_stats.get("achievements_unlocked"):
        session["player_stats"] = player_stats
    return redirect(url_for("index"))

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html", error="Internal server error"), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)