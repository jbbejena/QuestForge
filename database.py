
import sqlite3
import json
import logging
from typing import Dict, Any, Optional

class GameDatabase:
    def __init__(self, db_path: str = "game.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Players table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                session_id TEXT PRIMARY KEY,
                player_data TEXT NOT NULL,
                resources TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Game sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_sessions (
                session_id TEXT PRIMARY KEY,
                mission_data TEXT,
                story_data TEXT,
                turn_count INTEGER DEFAULT 0,
                score INTEGER DEFAULT 0,
                completed_missions TEXT,
                player_stats TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Story history table (for large story content)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS story_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                choice_made TEXT,
                story_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES players (session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_player_data(self, session_id: str, player_data: Dict[str, Any], resources: Dict[str, Any]):
        """Save player and resource data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO players 
            (session_id, player_data, resources, updated_at) 
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            session_id,
            json.dumps(player_data),
            json.dumps(resources)
        ))
        
        conn.commit()
        conn.close()
    
    def load_player_data(self, session_id: str) -> Optional[tuple]:
        """Load player and resource data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT player_data, resources FROM players WHERE session_id = ?',
            (session_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return (json.loads(result[0]), json.loads(result[1]))
        return None
    
    def save_game_session(self, session_id: str, mission_data: Dict[str, Any], 
                         story_data: Dict[str, Any], turn_count: int, 
                         score: int, completed_missions: list, player_stats: Dict[str, Any]):
        """Save game session data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO game_sessions 
            (session_id, mission_data, story_data, turn_count, score, 
             completed_missions, player_stats, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            session_id,
            json.dumps(mission_data) if mission_data else None,
            json.dumps(story_data),
            turn_count,
            score,
            json.dumps(completed_missions),
            json.dumps(player_stats)
        ))
        
        conn.commit()
        conn.close()
    
    def load_game_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load game session data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT mission_data, story_data, turn_count, score, 
                   completed_missions, player_stats 
            FROM game_sessions WHERE session_id = ?
        ''', (session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'mission_data': json.loads(result[0]) if result[0] else None,
                'story_data': json.loads(result[1]),
                'turn_count': result[2],
                'score': result[3],
                'completed_missions': json.loads(result[4]),
                'player_stats': json.loads(result[5])
            }
        return None
    
    def save_story_turn(self, session_id: str, turn_number: int, 
                       choice_made: str, story_content: str):
        """Save individual story turn to prevent cookie overflow."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO story_history 
            (session_id, turn_number, choice_made, story_content) 
            VALUES (?, ?, ?, ?)
        ''', (session_id, turn_number, choice_made, story_content))
        
        conn.commit()
        conn.close()
    
    def get_story_history(self, session_id: str, limit: int = 5) -> list:
        """Get recent story history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT turn_number, choice_made, story_content 
            FROM story_history 
            WHERE session_id = ? 
            ORDER BY turn_number DESC 
            LIMIT ?
        ''', (session_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'turn': row[0],
                'choice': row[1],
                'content': row[2]
            } for row in reversed(results)
        ]
    
    def cleanup_old_sessions(self, days_old: int = 7):
        """Clean up old game sessions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM players 
            WHERE created_at < datetime('now', '-{} days')
        '''.format(days_old))
        
        cursor.execute('''
            DELETE FROM game_sessions 
            WHERE created_at < datetime('now', '-{} days')
        '''.format(days_old))
        
        cursor.execute('''
            DELETE FROM story_history 
            WHERE created_at < datetime('now', '-{} days')
        '''.format(days_old))
        
        conn.commit()
        conn.close()

# Global database instance
db = GameDatabase()
