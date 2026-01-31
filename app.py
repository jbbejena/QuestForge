import os
import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session
from dotenv import load_dotenv

# --- MODULAR IMPORTS ---
# Integrating the separate logic files you created
from config import RANKS, CLASSES, WEAPONS, MISSIONS
from database import db
from story_manager import StoryManager
import game_logic
from achievements import initialize_player_stats

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# --- SERVER-SIDE SESSION CONFIGURATION ---
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_FILE_DIR"] = "./flask_session"
app.config["SESSION_FILE_THRESHOLD"] = 500
Session(app)

# --- INITIALIZATION ---
# Initialize OpenAI Client & Story Manager
try:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        client = OpenAI(api_key=api_key)
        # Inject client into StoryManager
        story_manager = StoryManager(ai_client=client)
        logger.info("AI Subsystems Online.")
    else:
        client = None
        story_manager = StoryManager(ai_client=None)
        logger.warning("OpenAI API Key missing. Running in fallback mode.")
except ImportError:
    client = None
    story_manager = StoryManager(ai_client=None)
    logger.warning("OpenAI library not found. Running in fallback mode.")


# --- HELPERS ---

def sync_to_database():
    """Helper to save current session state to the database."""
    try:
        if "session_id" not in session:
            session["session_id"] = game_logic.get_session_id()

        # Save Player Data
        db.save_player_data(
            session["session_id"],
            session.get("player", {}),
            session.get("resources", {})
        )

        # Save Game Session Data
        db.save_game_session(
            session_id=session["session_id"],
            mission_data=session.get("mission", {}),
            story_data={"full_text": session.get("story", "")}, # Wrap string in dict for consistency
            turn_count=session.get("turn_count", 0),
            score=session.get("score", 0),
            completed_missions=session.get("completed", []),
            player_stats=session.get("player_stats", {})
        )
    except Exception as e:
        logger.error(f"Database sync failed: {e}")

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
    # Initialize basic state
    player_stats = session.get("player_stats", initialize_player_stats())
    session.clear()
    session["player_stats"] = player_stats
    session["turn_count"] = 0

    # Create Player Object
    player_class = request.form.get("char_class", "Rifleman")
    session["player"] = {
        "name": request.form.get("name", "Rookie").strip() or "Rookie",
        "rank": request.form.get("rank", "Private"),
        "class": player_class,
        "weapon": request.form.get("weapon", "Rifle"),
        "health": 100,
        "max_health": 100
    }

    # Generate Squad based on Rank (using game_logic)
    session["squad"] = game_logic.generate_squad_members(session["player"])

    # Initialize Resources
    session["resources"] = {"medkit": 2, "grenade": 2, "ammo": 12}
    session["completed"] = []
    session["score"] = 0

    sync_to_database()
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
    chosen_mission_name = request.form.get("mission")
    mission = next((m for m in MISSIONS if m["name"] == chosen_mission_name), MISSIONS[0])
    session["mission"] = mission
    session["turn_count"] = 0

    # Generate Opening using StoryManager
    # We pass 'start' as the choice to indicate a new mission
    opening_text = story_manager.generate_story_continuation(
        mission=mission,
        player=session["player"],
        current_story="",
        choice="Mission Start"
    )

    session["story"] = opening_text
    session["last_response"] = opening_text

    sync_to_database()
    return redirect(url_for("play"))

@app.route("/play")
def play():
    full_story = session.get("story", "")
    last_response = session.get("last_response", "")

    if not full_story:
        return redirect(url_for("mission_menu"))

    # Logic to split static history vs animated new text
    if last_response and last_response in full_story:
        history = full_story[:-len(last_response)]
    else:
        history = ""
        last_response = full_story

    # Use robust extraction from game_logic
    choices_dict = game_logic.extract_choices_from_story(last_response)
    # Convert dict {1: "Go", 2: "Stay"} to list ["Go", "Stay"] for the template
    choices_list = list(choices_dict.values())

    # Fallback if extraction fails
    if not choices_list:
        choices_list = ["Press forward.", "Hold position.", "Check map."]

    return render_template("play.html", 
                         history=history,
                         new_text=last_response,
                         choices=choices_list,
                         player=session.get("player", {}), 
                         resources=session.get("resources", {}),
                         mission=session.get("mission", {}))

@app.route("/make_choice", methods=["POST"])
def make_choice():
    try:
        # 1. Parse User Input
        choice_index = int(request.form.get("choice", "1"))
        current_story = session.get("story", "")

        # Get the specific text of the choice made
        choices_dict = game_logic.extract_choices_from_story(session.get("last_response", ""))
        # Handle 0-based index from frontend vs 1-based index in dict
        chosen_action = choices_dict.get(choice_index, "Proceed cautiously")

        # Update History
        user_action_text = f"\n\n> **Order:** {chosen_action}\n"
        full_story_so_far = current_story + user_action_text
        session["turn_count"] = session.get("turn_count", 0) + 1

        # 2. Game Logic: Determine Outcome
        mission = session.get("mission")
        player = session.get("player")

        # Check for mission end scenarios using game_logic
        outcome = game_logic.detect_mission_outcome(full_story_so_far)

        if outcome == "success":
            session["score"] += 100
            sync_to_database()
            return redirect(url_for("mission_menu")) # Or a victory page
        elif outcome == "failure":
            sync_to_database()
            return redirect(url_for("game_over"))

        # 3. Generate Continuation (AI)
        next_chunk = story_manager.generate_story_continuation(
            mission=mission,
            player=player,
            current_story=full_story_so_far,
            choice=chosen_action
        )

        # 4. Handle Combat (if AI describes it)
        # Using the simplified check from game_logic for now, 
        # but you can expand this to use resolve_combat_encounter fully
        if any(k in next_chunk.lower() for k in game_logic.COMBAT_KEYWORDS):
             # Simple random damage for now to keep game flow
             combat_result = game_logic.resolve_combat_encounter(player, chosen_action, mission)
             if not combat_result["victory"]:
                 player["health"] -= combat_result["damage"]
                 next_chunk += f"\n\n(Combat Report: You took {combat_result['damage']} damage during the engagement.)"

        # 5. Update Session
        session["player"] = player
        session["story"] = full_story_so_far + next_chunk
        session["last_response"] = next_chunk

        # 6. Database Sync
        sync_to_database()

        if player["health"] <= 0:
            return redirect(url_for("game_over"))

        return redirect(url_for("play"))

    except Exception as e:
        logger.error(f"Error in make_choice: {e}")
        return redirect(url_for("play"))

@app.route("/use_item", methods=["POST"])
def use_item():
    item = request.form.get("item")
    resources = session.get("resources", {})
    player = session.get("player", {})

    if item == "medkit" and resources.get("medkit", 0) > 0:
        heal_amount = 30
        player["health"] = min(player.get("max_health", 100), player.get("health", 0) + heal_amount)
        resources["medkit"] -= 1

        session["player"] = player
        session["resources"] = resources
        sync_to_database()

        return jsonify({"success": True, "message": f"Used medkit. Restored {heal_amount} health.", "health": player["health"]})

    return jsonify({"success": False, "message": "Cannot use that item right now."})

@app.route("/game_over")
def game_over():
    return render_template("game_over.html", 
                         player=session.get("player", {}),
                         score=session.get("score", 0))

@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
