"""
Mission Generation Module
Handles dynamic mission creation and campaign progression
"""

import random
import logging
from typing import Dict, Any, List, Optional
from flask import session

# Mission templates for different phases of WWII
MISSION_TEMPLATES = {
    "normandy": [
        {
            "name": "Operation Overlord - D-Day",
            "location": "Omaha Beach, Normandy",
            "objective": "Secure the beach and establish a foothold in Nazi-occupied Europe",
            "difficulty": "Hard",
            "date": "June 6, 1944",
            "description": "Storm the beaches of Normandy with your squad. The fate of Europe hangs in the balance.",
            "is_campaign_start": True
        }
    ],
    "france": [
        {
            "name": "Liberation of Carentan",
            "location": "Carentan, France", 
            "objective": "Capture the strategic crossroads town",
            "difficulty": "Medium",
            "description": "Advance inland and capture this crucial transportation hub."
        },
        {
            "name": "Breakout from Normandy",
            "location": "Saint-Lô, France",
            "objective": "Break through German defensive lines",
            "difficulty": "Hard", 
            "description": "Support Operation Cobra by breaking German resistance."
        }
    ],
    "belgium": [
        {
            "name": "Liberation of Brussels",
            "location": "Brussels, Belgium",
            "objective": "Liberate the Belgian capital",
            "difficulty": "Medium",
            "description": "Push into Belgium and free Brussels from German occupation."
        },
        {
            "name": "Battle of the Bulge",
            "location": "Ardennes, Belgium",
            "objective": "Repel German counter-offensive",
            "difficulty": "Hard",
            "description": "Hold the line against Germany's desperate winter offensive."
        }
    ],
    "germany": [
        {
            "name": "Crossing the Rhine",
            "location": "Rhine River, Germany",
            "objective": "Establish bridgehead across the Rhine",
            "difficulty": "Hard",
            "description": "Cross Germany's last natural barrier and advance into the heartland."
        },
        {
            "name": "Liberation of Concentration Camp",
            "location": "Bavaria, Germany",
            "objective": "Liberate prisoners from Nazi camp",
            "difficulty": "Medium",
            "description": "Discover and liberate survivors from Nazi atrocities."
        }
    ]
}

def generate_next_mission(ai_client=None) -> Dict[str, Any]:
    """Generate the next mission in the campaign based on previous outcomes."""
    campaign = session.get("campaign", {})
    completed = campaign.get("completed_missions", [])
    current_date = campaign.get("campaign_date", "June 6, 1944")
    
    # Determine campaign phase based on progress
    mission_count = len(completed)
    if mission_count == 0:
        # Always start with D-Day
        return MISSION_TEMPLATES["normandy"][0].copy()
    
    # Determine current theater
    if mission_count <= 3:
        theater = "france"
    elif mission_count <= 6:
        theater = "belgium"  
    else:
        theater = "germany"
    
    # Try AI generation first if available
    if ai_client:
        try:
            ai_mission = generate_ai_mission(ai_client, completed, current_date, theater)
            if ai_mission:
                return ai_mission
        except Exception as e:
            logging.warning(f"AI mission generation failed: {e}")
    
    # Fallback to templates
    available_missions = MISSION_TEMPLATES.get(theater, MISSION_TEMPLATES["france"])
    return random.choice(available_missions).copy()

def generate_ai_mission(ai_client, completed_missions: List[Dict], current_date: str, theater: str) -> Optional[Dict[str, Any]]:
    """Generate mission using AI based on campaign context."""
    # Build context from previous missions
    context = f"Theater: {theater.title()}, Missions completed: {len(completed_missions)}, Current date: {current_date}"
    
    if completed_missions:
        last_mission = completed_missions[-1]
        context += f" Last mission: {last_mission.get('name', 'Unknown')} - {last_mission.get('outcome', 'completed')}"
    
    system_msg = (
        "You are a WWII campaign mission generator. Create the next logical mission "
        f"in the {theater} theater following previous missions. Generate realistic WWII operations "
        "that progress the Allied advance through Europe. Consider historical accuracy, "
        "tactical progression, and narrative continuity."
    )
    
    user_prompt = (
        f"{context}\n\n"
        "Generate the next mission with this EXACT format:\n"
        "NAME: [Mission name]\n"
        "LOCATION: [Specific location]\n"  
        "DATE: [Date in format Month Day, Year]\n"
        "OBJECTIVE: [Clear military objective in one sentence]\n"
        "DIFFICULTY: [Easy/Medium/Hard]\n"
        "DESCRIPTION: [2-3 sentence briefing]"
    )
    
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        ai_response = response.choices[0].message.content
        return parse_ai_mission_response(ai_response, current_date)
        
    except Exception as e:
        logging.error(f"AI mission generation error: {e}")
        return None

def parse_ai_mission_response(response: str, fallback_date: str) -> Dict[str, Any]:
    """Parse AI mission response into structured data."""
    mission = {
        "name": "Liberation Mission",
        "desc": "Continue the Allied advance through Europe.",
        "difficulty": "Medium", 
        "location": "Western Front",
        "date": fallback_date,
        "objective": "Complete assigned objectives"
    }
    
    try:
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("NAME:"):
                mission["name"] = line.replace("NAME:", "").strip()
            elif line.startswith("LOCATION:"):
                mission["location"] = line.replace("LOCATION:", "").strip()
            elif line.startswith("DATE:"):
                date = line.replace("DATE:", "").strip()
                mission["date"] = date
                # Update campaign date
                campaign = session.get("campaign", {})
                campaign["campaign_date"] = date
                session["campaign"] = campaign
            elif line.startswith("OBJECTIVE:"):
                mission["objective"] = line.replace("OBJECTIVE:", "").strip()
            elif line.startswith("DIFFICULTY:"):
                difficulty = line.replace("DIFFICULTY:", "").strip()
                if difficulty in ["Easy", "Medium", "Hard"]:
                    mission["difficulty"] = difficulty
            elif line.startswith("DESCRIPTION:"):
                mission["desc"] = line.replace("DESCRIPTION:", "").strip()
                
    except Exception as e:
        logging.warning(f"Mission parsing error: {e}")
    
    return mission

def get_mission_briefing_context(mission: Dict[str, Any], player: Dict[str, Any]) -> str:
    """Generate contextual mission briefing."""
    briefing_parts = [
        f"MISSION: {mission.get('name', 'Unknown Operation')}",
        f"LOCATION: {mission.get('location', 'Classified')}",
        f"DATE: {mission.get('date', 'Unknown')}",
        f"DIFFICULTY: {mission.get('difficulty', 'Medium')}",
        "",
        f"SOLDIER: {player.get('rank', 'Private')} {player.get('name', 'Unknown')}",
        f"SPECIALIZATION: {player.get('class', 'Infantry')}",  
        f"PRIMARY WEAPON: {player.get('weapon', 'M1 Garand')}",
        "",
        "MISSION BRIEFING:",
        mission.get('desc', 'No briefing available.'),
        "",
        f"OBJECTIVE: {mission.get('objective', 'Complete assigned tasks.')}"
    ]
    
    return "\n".join(briefing_parts)

def calculate_mission_difficulty_modifier(difficulty: str) -> float:
    """Get difficulty modifier for various calculations."""
    modifiers = {
        "easy": 1.2,
        "medium": 1.0,
        "hard": 0.8
    }
    return modifiers.get(difficulty.lower(), 1.0)

def get_historical_context(mission_name: str) -> str:
    """Provide historical context for missions."""
    historical_contexts = {
        "operation overlord": "The largest amphibious invasion in history, involving over 150,000 Allied troops.",
        "liberation of carentan": "A crucial crossroads town that controlled access to the Cotentin Peninsula.",
        "battle of the bulge": "Germany's last major offensive on the Western Front during winter 1944-45.",
        "crossing the rhine": "Breaking through Germany's final natural defensive barrier.",
        "liberation of brussels": "The liberation of Belgium's capital marked the collapse of German defenses in the Low Countries."
    }
    
    for key, context in historical_contexts.items():
        if key in mission_name.lower():
            return context
    
    return "Another crucial operation in the liberation of Europe from Nazi occupation."

# Predefined mission sequences for consistent campaign flow
CAMPAIGN_SEQUENCES = {
    "western_front": [
        "normandy_landings",
        "carentan_capture", 
        "normandy_breakout",
        "paris_liberation",
        "belgian_advance",
        "battle_of_bulge",
        "rhine_crossing",
        "germany_advance",
        "concentration_camp",
        "berlin_approach"
    ]
}

def get_next_sequence_mission(sequence_name: str = "western_front") -> Optional[str]:
    """Get the next mission in a predefined sequence."""
    campaign = session.get("campaign", {})
    completed = campaign.get("completed_missions", [])
    sequence = CAMPAIGN_SEQUENCES.get(sequence_name, [])
    
    completed_count = len(completed)
    if completed_count < len(sequence):
        return sequence[completed_count]
    
    return None