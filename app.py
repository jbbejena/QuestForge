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
# This fixes the "Cookie Overflow" and "Looping" bugs
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

# Game Data
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

SURPRISE_COMBAT_KEYWORDS = [
    "combat", "ambush", "ambushed", "attack begins", "sudden attack", "under fire",
    "opens fire", "open fire", "firefight", "enemy fires", "battle erupts",
    "exchange of gunfire", "hostilities commence", "start shooting", "start firing",
    "enemy spotted", "take cover", "incoming fire", "gunshots ring out"
]

# --- HELPER FUNCTIONS ---

def ai_chat(system_msg: str, user_prompt: str, temperature: float = 0.8, max_tokens: int = 700) -> str:
    """Call OpenAI API to generate story content."""
    if client is None:
        # Fallback for when AI is offline
        return "Radio silence. (AI not configured)\n\n1. Advance cautiously.\n2. Hold position.\n3. Retreat to cover."

    try:
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
        return "(Communication disrupted)\n\n1. Check Radio\n2. Wait\n3. Signal Manually"

def parse_choices(text: str):
    """
    Extract ONLY the LAST set of numbered choices from the text.
    This fixes the issue where combat logs or history confused the buttons.
    """
    lines = text.splitlines()
    choices = []

    # Iterate backwards to find the last set of choices
    # We look for lines starting with "1.", "2.", "3."
    for line in reversed(lines):
        match = re.match(r"^\s*([1-3])[\.\)\-\:]\s*(.+)", line)
        if match:
            # Insert at beginning since we are reading backwards
            choices.insert(0, match.group(2).strip())

        # If we have collected a full set of 3, we stop. 
        # This prevents picking up choices from previous turns.
        if len(choices) >= 3:
            break

    # Fallback: if we didn't find them backwards, try forwards (rare)
    if len(choices) < 3:
        choices = []
        for line in lines:
            match = re.match(r"\s*([1-3])[\.\)]\s*(.+)", line)
            if match:
                choices.append(match.group(2).strip())

    # Final Fallback if AI failed completely
    while len(choices) < 3:
        choices.append("Press forward.")

    # Ensure we return exactly the last 3 found
    return choices[-3:]

def resolve_combat(story_so_far, player, resources):
    """
    Calculates combat result and generates the aftermath.
    Returns: (Full Story Text, The New Chunk Only)
    """
    # Simple combat logic
    won = random.random() > 0.3  # 70% win rate
    damage = random.randint(5, 20)
    player["health"] = max(0, player["health"] - damage)

    result_text = f"\n\n[COMBAT ENCOUNTER]\n"
    if won:
        result_text += f"Victory! Enemy neutralized. You took {damage} damage.\n"
        session["battles_won"] = session.get("battles_won", 0) + 1
        session["score"] = session.get("score", 0) + 50
    else:
        result_text += f"Ambush! You were forced to retreat, taking {damage} damage.\n"

    # Generate choices for AFTER combat
    aftermath_prompt = f"{story_so_far}\n{result_text}\n\nWrite the immediate aftermath and 3 new tactical choices."
    aftermath_choices = ai_chat("Game Master. Write aftermath + 3 choices.", aftermath_prompt)

    full_text = story_so_far + result_text + aftermath_choices
    new_chunk = result_text + aftermath_choices

    return full_text, new_chunk

# --- ROUTES ---

@app.route("/")
def index():
    if "player_stats" not in session:
        session["player_stats"] = initialize_player_stats()
    return render_template("index.html", 
                         ranks=RANKS, 
                         classes=CLASSES, 
                         weapons=WEAPONS,
                         achievements_count=len(session.get("player_stats", {}).get("achievements_unlocked", [])))

@app.route("/create_character", methods=["POST"])
def create_character():
    player_stats = session.get("player_stats", initialize_player_stats())
    session.clear()
    session["player_stats"] = player_stats

    player_class = request.form.get("char_class", "Rifleman")
    session["player"] = {
        "name": request.form.get("name", "Rookie").strip() or "Rookie",
        "rank": request.form.get("rank", "Private"),
        "class": player_class,
        "weapon": request.form.get("weapon", "Rifle"),
        "health": 100,
        "max_health": 100
    }
    session["resources"] = {"medkit": 2, "grenade": 2, "ammo": 12}
    session["squad"] = ["Smith (Medic)", "Johnson (Gunner)", "Williams (Sniper)"]
    session["completed"] = []
    session["score"] = 0
    return redirect(url_for("mission_menu"))

@app.route("/missions")
def mission_menu():
    return render_template("missions.html", 
                         missions=MISSIONS, 
                         player=session.get("player"),
                         score=session.get("score", 0),
                         achievements_count=len(session.get("player_stats", {}).get("achievements_unlocked", [])))

@app.route("/start_mission", methods=["POST"])
def start_mission():
    chosen_mission = request.form.get("mission")
    mission = next((m for m in MISSIONS if m["name"] == chosen_mission), MISSIONS[0])
    session["mission"] = mission

    player = session.get("player", {})
    squad = session.get("squad", [])

    system_msg = "You are a WWII text-adventure game master. Create an immersive opening."
    user_prompt = f"Mission: {mission['name']}. Player: {player['rank']} {player['name']}. Squad: {', '.join(squad)}. Write opening with 3 choices."

    story = ai_chat(system_msg, user_prompt)
    session["story"] = story
    session["last_response"] = story # Track the newest text chunk for animation

    return redirect(url_for("play"))

@app.route("/play")
def play():
    full_story = session.get("story", "")
    last_response = session.get("last_response", "")

    if not full_story:
        return redirect(url_for("mission_menu"))

    # Logic to split static history vs animated new text
    if last_response and last_response in full_story:
        # History is everything BEFORE the last response
        history = full_story[:-len(last_response)]
    else:
        history = ""
        last_response = full_story

    choices = parse_choices(full_story)

    return render_template("play.html", 
                         history=history,
                         new_text=last_response,
                         choices=choices,
                         player=session.get("player", {}), 
                         resources=session.get("resources", {}),
                         mission=session.get("mission", {}))

@app.route("/make_choice", methods=["POST"])
def make_choice():
    try:
        choice_index = int(request.form.get("choice", "1")) - 1
        current_story = session.get("story", "")
        choices = parse_choices(current_story)

        # Get the text of the choice the user made
        chosen_action = choices[choice_index] if 0 <= choice_index < len(choices) else "Continue..."

        # 1. Append player choice to story (This is "history" now)
        user_action_text = f"\n\n> **Order:** {chosen_action}\n"
        current_story += user_action_text

        # 2. Random Event Logic (Damage)
        player = session.get("player")
        damage = 0
        if random.random() < 0.35: # 35% chance of taking damage moving between points
            damage = random.randint(5, 15)
            player["health"] = max(0, player["health"] - damage)
            current_story += f"\n(Event: You took {damage} damage during the maneuver.)\n"
        session["player"] = player

        if player["health"] <= 0:
            return redirect(url_for("game_over"))

        # 3. Generate Next Scenario
        system_msg = "Continue the story. 1-2 paragraphs. End with 3 numbered choices."
        prompt = f"Context:\n{current_story[-2000:]}\n\nAction taken: {chosen_action}. Status: Health {player['health']}."

        next_scenario = ai_chat(system_msg, prompt)

        # 4. Check for Surprise Combat
        if any(k in next_scenario.lower() for k in SURPRISE_COMBAT_KEYWORDS):
            # If combat, we strip the choices the AI just made, because we need to resolve combat first.
            lines = next_scenario.splitlines()
            # Remove lines that look like choices
            clean_lines = [l for l in lines if not re.match(r"^\s*[1-3][\.\)]", l)]
            next_scenario_cleaned = "\n".join(clean_lines)

            # Combine current story + cleaned scenario + combat result + new choices
            story_so_far = current_story + "\n" + next_scenario_cleaned
            full_text_after_combat, combat_update = resolve_combat(story_so_far, player, session.get("resources"))

            # Save state
            session["story"] = full_text_after_combat
            # The animated text is the scenario + combat result
            session["last_response"] = next_scenario_cleaned + "\n" + combat_update

        else:
            # Normal progression
            session["story"] = current_story + "\n" + next_scenario
            # The animated text is just the new scenario
            session["last_response"] = "\n" + next_scenario

        return redirect(url_for("play"))

    except Exception as e:
        logging.error(f"Error in make_choice: {e}")
        # If something breaks, try to reload play page so user isn't stuck
        return redirect(url_for("play"))

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

        session["player"] = player
        session["resources"] = resources

        return jsonify({"success": True, "message": f"Used medkit. Restored {heal_amount} health.", "health": player["health"]})

    return jsonify({"success": False, "message": "Cannot use that item right now."})

@app.route("/game_over")
def game_over():
    return render_template("game_over.html", 
                         player=session.get("player", {}),
                         score=session.get("score", 0))

@app.route("/base")
def base():
    return render_template("base.html", player=session.get("player"))

@app.route("/achievements")
def achievements():
    return render_template("achievements.html", 
                         player_stats=session.get("player_stats", {}), 
                         achievements=[], new_achievements=[])

@app.route("/reset")
def reset():
    """Reset game session."""
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)