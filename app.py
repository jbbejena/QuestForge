import os
import random
import re
import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv

from config import (
    RANKS, CLASSES, WEAPONS, INITIAL_MISSION, DIFFICULTY_SETTINGS,
    SESSION_CONFIG, AI_CONFIG, get_env_config
)
from session_manager import session_manager
from story_manager import story_manager
from database import db
from replit_session_manager import (
    replit_session, set_story_data, get_story_data, get_game_state, get_player_data
)
from achievements import (
    check_achievements, get_achievement_display, initialize_player_stats, 
    update_player_stats, ACHIEVEMENTS
)
from game_logic import (
    get_session_id, resolve_combat_encounter, detect_mission_outcome,
    extract_choices_from_story, validate_game_state, calculate_mission_score,
    get_fallback_story, COMBAT_KEYWORDS
)

logging.basicConfig(level=logging.DEBUG)
load_dotenv()
env_config = get_env_config()

app = Flask(__name__)
app.secret_key = env_config["session_secret"]
app.permanent_session_lifetime = SESSION_CONFIG["permanent_session_lifetime"]
app.config['SESSION_PERMANENT'] = True

try:
    from openai import OpenAI
    client = OpenAI(api_key=env_config["openai_api_key"])
    story_manager.client = client
except Exception as e:
    client = None
    logging.warning(f"OpenAI error: {e}")

def ai_chat(system_msg, user_prompt, temperature=0.8, max_tokens=700):
    if client is None:
        return get_fallback_story(session.get("turn_count", 0))
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
        logging.error(f"AI error: {e}")
        return get_fallback_story(session.get("turn_count", 0))

def parse_choices(text):
    if not text: return ["Advance.", "Observe.", "Regroup."]
    matches = re.findall(r"^\s*([1-3])[\.\)\-\:\s]+(.+)", text, re.MULTILINE)
    choices = [m[1].strip() for m in matches]
    while len(choices) < 3: choices.append("Continue mission")
    return choices[:3]

def generate_contextual_choices(player, mission, turn_count):
    return ["Advance cautiously", "Scout ahead", "Hold position"]

def generate_dynamic_consequences(choice, player, resources, mission, turn):
    return ""

def save_to_database():
    sid = get_session_id()
    db.save_player_data(sid, session.get("player", {}), session.get("resources", {}))
    db.save_game_session(sid, session.get("mission", {}), {}, session.get("turn_count", 0), session.get("score", 0), session.get("completed", []), session.get("player_stats", {}))

def load_from_database():
    sid = get_session_id()
    p = db.load_player_data(sid)
    if p: session["player"], session["resources"] = p
    g = db.load_game_session(sid)
    if g:
        session["mission"] = g["mission_data"]
        session["turn_count"] = g["turn_count"]
        session["score"] = g["score"]
        session["completed"] = g["completed_missions"]
        session["player_stats"] = g["player_stats"]

@app.route("/")
def index():
    load_from_database()
    if "player_stats" not in session: session["player_stats"] = initialize_player_stats()
    return render_template("index.html", ranks=RANKS, classes=CLASSES, weapons=WEAPONS, achievements_count=len(session["player_stats"].get("achievements_unlocked", [])))

@app.route("/create_character", methods=["POST"])
def create_character():
    stats = session.get("player_stats", initialize_player_stats())
    session.clear()
    session["player_stats"] = stats
    session["player"] = {"name": request.form.get("name", "Rookie"), "rank": request.form.get("rank", "Private"), "class": request.form.get("char_class", "Rifleman"), "weapon": request.form.get("weapon", "Rifle"), "health": 100, "max_health": 100, "morale": 100}
    session["resources"] = {"medkit": 2, "grenade": 2, "ammo": 12}
    session["squad"] = ["Thompson", "Garcia", "Kowalski"]
    session["completed"] = []
    session["score"] = 0
    session["missions_completed"] = 0
    session["turn_count"] = 0
    return redirect(url_for("mission_menu"))

@app.route("/missions")
def mission_menu():
    if "player" not in session: return redirect(url_for("index"))
    return render_template("missions.html", mission=INITIAL_MISSION, player=session["player"], squad=session.get("squad", []), score=session.get("score", 0), achievements_count=len(session.get("player_stats", {}).get("achievements_unlocked", [])), mission_number=session.get("missions_completed", 0) + 1)

@app.route("/start_mission", methods=["POST"])
def start_mission():
    mission = INITIAL_MISSION
    session["mission"] = mission
    session["turn_count"] = 0
    session["base_story"] = ""
    session["new_content"] = ""
    
    player = session["player"]
    squad = session.get("squad", [])
    
    sys_msg = "WWII narrator. End with 3 numbered choices."
    prompt = f"Start mission: {mission['name']}. Player: {player['rank']} {player['name']}"
    story = ai_chat(sys_msg, prompt)
    
    session["story"] = story
    set_story_data(story)
    return redirect(url_for("play"))

@app.route("/play")
def play():
    story = get_story_data("") or session.get("story", "")
    if not story: return redirect(url_for("mission_menu"))
    choices = parse_choices(story)
    return render_template("play.html", story=story, base_story=session.get("base_story", ""), new_content=session.get("new_content", ""), choices=choices, player=session.get("player"), resources=session.get("resources"), mission=session.get("mission"), turn_count=session.get("turn_count", 0), squad=session.get("squad", []))

@app.route("/choose", methods=["POST"])
def make_choice():
    try:
        choice_idx = int(request.form.get("choice", "1")) - 1
        current_story = get_story_data("") or session.get("story", "")
        choices = parse_choices(current_story)
        chosen_action = choices[choice_idx] if 0 <= choice_idx < len(choices) else "Continue"
        
        turn = session.get("turn_count", 0) + 1
        session["turn_count"] = turn
        
        prompt = f"Player chose: {chosen_action}. Continue WWII story. End with 3 choices."
        new_text = ai_chat("WWII narrator", prompt)
        
        full_story = current_story + f"\n\n> {chosen_action}\n\n" + new_text
        session["story"] = full_story
        session["base_story"] = current_story
        session["new_content"] = new_text
        set_story_data(full_story)
        
        outcome = detect_mission_outcome(full_story)
        if outcome:
            session["mission_outcome"] = outcome
            return redirect(url_for("mission_complete"))
            
        save_to_database()
        return redirect(url_for("play"))
    except Exception as e:
        logging.error(f"Choice error: {e}")
        return redirect(url_for("play"))

@app.route("/mission_complete")
def mission_complete():
    mission = session.get("mission", {})
    outcome = session.get("mission_outcome", "success")
    session["missions_completed"] = session.get("missions_completed", 0) + 1
    session["score"] = session.get("score", 0) + 100
    return render_template("mission_complete.html", mission=mission, outcome=outcome, player=session.get("player"), score=session.get("score", 0))

@app.route("/reset")
def reset():
    stats = session.get("player_stats")
    session.clear()
    session["player_stats"] = stats
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
