import os, random
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from ai_editor import plan_changes, apply_changes, try_git_commit

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")  # OK for dev

# ----------------------------
# Simple in-memory/session "game state"
# ----------------------------

DEFAULT_MISSIONS = [
    {"name": "Storm the Beach", "difficulty": "Easy",
     "desc": "Land on Normandy and secure the beachhead."},
    {"name": "Sabotage the Bridge", "difficulty": "Medium",
     "desc": "Destroy the supply bridge to slow enemy reinforcements."},
    {"name": "Rescue the POWs", "difficulty": "Hard",
     "desc": "Sneak behind lines and rescue captured soldiers."},
]

def get_state():
    if "game" not in session:
        session["game"] = {
            "player": {"name": "Johnson", "rank": "Private", "class": "Infantry",
                       "weapon": "M1 Garand", "health": 85, "max_health": 100,
                       "morale": 80, "special_ability": "Focused Fire"},
            "missions": DEFAULT_MISSIONS,
            "current_mission": None,
            "score": 120,
            "achievements": [],
            "squad": ["Miller", "Davis", "Garcia"],
            "resources": {"ammo": 20, "medkit": 2, "grenade": 1, "intel": 1},
            "story": "",
            "choices": []
        }
    return session["game"]

# ----------------------------
# GAME ROUTES
# ----------------------------

@app.route("/")
def index():
    g = get_state()
    # Check if player already exists
    if g["player"]["name"] != "Johnson":  # Default name means not customized
        return redirect(url_for("mission_menu"))
    
    # Show character creation
    ranks = ["Private", "Corporal", "Sergeant", "Lieutenant", "Captain"]
    classes = ["Infantry", "Medic", "Engineer", "Sniper", "Support"]
    weapons = ["M1 Garand", "Thompson SMG", "BAR", "Springfield", "M1 Carbine"]
    
    return render_template("index.html", 
                         ranks=ranks, 
                         classes=classes, 
                         weapons=weapons,
                         achievements_count=len(g["achievements"]))

@app.route("/create_character", methods=["POST"])
def create_character():
    g = get_state()
    
    # Get form data
    name = request.form.get("name", "Soldier").strip()[:20]
    rank = request.form.get("rank", "Private")
    char_class = request.form.get("char_class", "Infantry")
    weapon = request.form.get("weapon", "M1 Garand")
    
    # Update player
    g["player"].update({
        "name": name,
        "rank": rank,
        "class": char_class,
        "weapon": weapon,
        "health": 100,
        "max_health": 100,
        "morale": 80
    })
    
    session.modified = True
    return redirect(url_for("mission_menu"))

@app.route("/missions")
def mission_menu():
    g = get_state()
    achievements_count = len(g["achievements"])
    return render_template("missions.html",
        missions=g["missions"],
        player=g["player"],
        score=g["score"],
        achievements_count=achievements_count
    )

@app.route("/start_mission", methods=["POST"])
def start_mission():
    g = get_state()
    name = request.form.get("mission", "")
    g["current_mission"] = {"name": name}
    g["story"] = "Mission started: " + name + "\nRadio: Stay sharp, soldier."
    g["choices"] = ["Advance", "Call for artillery", "Regroup with squad"]
    session.modified = True
    return redirect(url_for("play"))

@app.route("/play")
def play():
    g = get_state()
    if not g["current_mission"]:
        return redirect(url_for("mission_menu"))
    return render_template("play.html",
        player=g["player"],
        mission=g["current_mission"],
        squad=g["squad"],
        resources=g["resources"],
        story=g["story"],
        base_story=None,
        new_content=None,
        choices=g["choices"]
    )

@app.route("/make_choice", methods=["POST"])
def make_choice():
    g = get_state()
    if not g["current_mission"]:
        return redirect(url_for("mission_menu"))

    choice_index = int(request.form.get("choice", "1")) - 1
    made = g["choices"][choice_index] if 0 <= choice_index < len(g["choices"]) else "Wait"

    # Tiny demo logic
    outcome = random.choice([
        "You push forward under fire.",
        "The bombardment clears a path.",
        "You regroup and steady your nerves.",
        "An enemy patrol spots you!"
    ])
    dmg = random.randint(0, 15)
    g["player"]["health"] = max(0, g["player"]["health"] - dmg)
    if g["resources"]["ammo"] > 0:
        g["resources"]["ammo"] -= 1

    base_story = g["story"]
    new_content = f"\n\nYou chose: {made}\n{outcome}\nYou took {dmg} damage."

    # Update state
    g["story"] = base_story + new_content
    g["choices"] = ["Advance again", "Flank left", "Hold position"]
    session.modified = True

    if g["player"]["health"] <= 0:
        return redirect(url_for("error_page"))

    # Render with base/new so the template can "type" the latest bit
    return render_template("play.html",
        player=g["player"], mission=g["current_mission"], squad=g["squad"],
        resources=g["resources"], story=None,
        base_story=base_story, new_content=new_content,
        choices=g["choices"]
    )

@app.route("/error")
def error_page():
    return render_template("error.html", error="You were incapacitated. Mission failed.")

@app.route("/achievements")
def achievements():
    g = get_state()
    return render_template("error.html", error=f"Achievements: {g['achievements'] or 'none yet'}")

@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("mission_menu"))

# ----------------------------
# AI HELPER ROUTES
# ----------------------------

@app.route("/admin/ai", methods=["GET"])
def ai_console():
    return render_template("ai_console.html")

@app.route("/admin/ai/plan", methods=["POST"])
def ai_plan():
    data = request.get_json(force=True)
    instruction = data.get("instruction", "").strip()
    if not instruction:
        return jsonify({"error":"Missing 'instruction'"}), 400
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
        return jsonify({"error":"Expected plan JSON with 'changes'"}), 400
    result = apply_changes(plan)
    try_git_commit(result["commit_message"])
    return jsonify({"result": result})

# ----------------------------
# ENTRYPOINT
# ----------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)