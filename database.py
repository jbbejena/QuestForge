
import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional

class GameDatabase:
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            # Fallback to SQLite if PostgreSQL not available
            import sqlite3
            self.use_sqlite = True
            self.db_path = "game.db"
            self.init_sqlite_database()
        else:
            self.use_sqlite = False
            self.init_postgresql_database()
    
    def get_connection(self):
        """Get database connection based on available database type."""
        if self.use_sqlite:
            import sqlite3

            return sqlite3.connect(self.db_path)
        else:
            return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
    
    def init_sqlite_database(self):
        """Initialize SQLite database tables with error handling."""
        import sqlite3
        try:
            # Try to remove corrupted database
            if os.path.exists(self.db_path):
                try:
                    conn = sqlite3.connect(self.db_path)
                    conn.execute("SELECT 1")
                    conn.close()
                except sqlite3.DatabaseError:
                    logging.warning("Removing corrupted SQLite database")
                    os.remove(self.db_path)
            
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
            
            # Story history table
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
            logging.info("SQLite database initialized successfully")
            
        except Exception as e:
            logging.error(f"SQLite initialization error: {e}")
            # Create minimal fallback
            try:
                conn = sqlite3.connect(":memory:")
                self.db_path = ":memory:"
                logging.warning("Using in-memory SQLite database as fallback")
            except Exception as fallback_error:
                logging.error(f"Failed to create fallback database: {fallback_error}")
                raise
    
    def init_postgresql_database(self):
        """Initialize PostgreSQL database tables."""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            # Players table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    session_id VARCHAR(255) PRIMARY KEY,
                    player_data TEXT NOT NULL,
                    resources TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Game sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    session_id VARCHAR(255) PRIMARY KEY,
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
            
            # Story history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS story_history (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    turn_number INTEGER NOT NULL,
                    choice_made TEXT,
                    story_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES players (session_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logging.info("PostgreSQL database initialized successfully")
            
        except Exception as e:
            logging.error(f"PostgreSQL initialization error: {e}")
            raise
    
    def save_player_data(self, session_id: str, player_data: Dict[str, Any], resources: Dict[str, Any]):
        """Save player and resource data."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute('''
                    INSERT OR REPLACE INTO players 
                    (session_id, player_data, resources, updated_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    session_id,
                    json.dumps(player_data),
                    json.dumps(resources)
                ))
            else:
                cursor.execute('''
                    INSERT INTO players 
                    (session_id, player_data, resources, updated_at) 
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (session_id) DO UPDATE SET
                    player_data = EXCLUDED.player_data,
                    resources = EXCLUDED.resources,
                    updated_at = CURRENT_TIMESTAMP
                ''', (
                    session_id,
                    json.dumps(player_data),
                    json.dumps(resources)
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error saving player data: {e}")
    
    def load_player_data(self, session_id: str) -> Optional[tuple]:
        """Load player and resource data."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute(
                    'SELECT player_data, resources FROM players WHERE session_id = ?',
                    (session_id,)
                )
            else:
                cursor.execute(
                    'SELECT player_data, resources FROM players WHERE session_id = %s',
                    (session_id,)
                )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                if self.use_sqlite:
                    return (json.loads(result[0]), json.loads(result[1]))
                else:
                    return (json.loads(result['player_data']), json.loads(result['resources']))
            return None
        except Exception as e:
            logging.error(f"Error loading player data: {e}")
            return None
    
    def save_game_session(self, session_id: str, mission_data: Dict[str, Any], 
                         story_data: Dict[str, Any], turn_count: int, 
                         score: int, completed_missions: list, player_stats: Dict[str, Any]):
        """Save game session data."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
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
            else:
                cursor.execute('''
                    INSERT INTO game_sessions 
                    (session_id, mission_data, story_data, turn_count, score, 
                     completed_missions, player_stats, updated_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (session_id) DO UPDATE SET
                    mission_data = EXCLUDED.mission_data,
                    story_data = EXCLUDED.story_data,
                    turn_count = EXCLUDED.turn_count,
                    score = EXCLUDED.score,
                    completed_missions = EXCLUDED.completed_missions,
                    player_stats = EXCLUDED.player_stats,
                    updated_at = CURRENT_TIMESTAMP
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
        except Exception as e:
            logging.error(f"Error saving game session: {e}")
    
    def load_game_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load game session data."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute('''
                    SELECT mission_data, story_data, turn_count, score, 
                           completed_missions, player_stats 
                    FROM game_sessions WHERE session_id = ?
                ''', (session_id,))
            else:
                cursor.execute('''
                    SELECT mission_data, story_data, turn_count, score, 
                           completed_missions, player_stats 
                    FROM game_sessions WHERE session_id = %s
                ''', (session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                if self.use_sqlite:
                    return {
                        'mission_data': json.loads(result[0]) if result[0] else None,
                        'story_data': json.loads(result[1]),
                        'turn_count': result[2],
                        'score': result[3],
                        'completed_missions': json.loads(result[4]),
                        'player_stats': json.loads(result[5])
                    }
                else:
                    return {
                        'mission_data': json.loads(result['mission_data']) if result['mission_data'] else None,
                        'story_data': json.loads(result['story_data']),
                        'turn_count': result['turn_count'],
                        'score': result['score'],
                        'completed_missions': json.loads(result['completed_missions']),
                        'player_stats': json.loads(result['player_stats'])
                    }
            return None
        except Exception as e:
            logging.error(f"Error loading game session: {e}")
            return None
    
    def save_story_turn(self, session_id: str, turn_number: int, 
                       choice_made: str, story_content: str):
        """Save individual story turn."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute('''
                    INSERT INTO story_history 
                    (session_id, turn_number, choice_made, story_content) 
                    VALUES (?, ?, ?, ?)
                ''', (session_id, turn_number, choice_made, story_content))
            else:
                cursor.execute('''
                    INSERT INTO story_history 
                    (session_id, turn_number, choice_made, story_content) 
                    VALUES (%s, %s, %s, %s)
                ''', (session_id, turn_number, choice_made, story_content))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error saving story turn: {e}")
    
    def get_story_context(self, session_id: str, limit: int = 3) -> str:
        """Get condensed story context."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute('''
                    SELECT choice_made, story_content 
                    FROM story_history 
                    WHERE session_id = ? 
                    ORDER BY turn_number DESC 
                    LIMIT ?
                ''', (session_id, limit))
            else:
                cursor.execute('''
                    SELECT choice_made, story_content 
                    FROM story_history 
                    WHERE session_id = %s 
                    ORDER BY turn_number DESC 
                    LIMIT %s
                ''', (session_id, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return ""
            
            context_parts = []
            for row in reversed(results):
                if self.use_sqlite:
                    choice, content = row[0], row[1]
                else:
                    choice, content = row['choice_made'], row['story_content']
                content_summary = content[:200].replace('\n', ' ')
                context_parts.append(f"Action: {choice} -> {content_summary}")
            
            return " | ".join(context_parts)
        except Exception as e:
            logging.error(f"Error getting story context: {e}")
            return ""
    
    def get_story_history(self, session_id: str, limit: int = 5) -> list:
        """Get recent story history."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute('''
                    SELECT turn_number, choice_made, story_content 
                    FROM story_history 
                    WHERE session_id = ? 
                    ORDER BY turn_number DESC 
                    LIMIT ?
                ''', (session_id, limit))
            else:
                cursor.execute('''
                    SELECT turn_number, choice_made, story_content 
                    FROM story_history 
                    WHERE session_id = %s 
                    ORDER BY turn_number DESC 
                    LIMIT %s
                ''', (session_id, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            history = []
            for row in reversed(results):
                if self.use_sqlite:
                    history.append({
                        'turn': row[0],
                        'choice': row[1],
                        'content': row[2]
                    })
                else:
                    history.append({
                        'turn': row['turn_number'],
                        'choice': row['choice_made'],
                        'content': row['story_content']
                    })
            
            return history
        except Exception as e:
            logging.error(f"Error getting story history: {e}")
            return []
    
    def save_story_chunk(self, session_id: str, chunk_id: str, content: str):
        """Save large story content in chunks."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS story_chunks (
                        session_id TEXT,
                        chunk_id TEXT,
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (session_id, chunk_id)
                    )
                ''')
                cursor.execute('''
                    INSERT OR REPLACE INTO story_chunks 
                    (session_id, chunk_id, content) 
                    VALUES (?, ?, ?)
                ''', (session_id, chunk_id, content))
            else:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS story_chunks (
                        session_id VARCHAR(255),
                        chunk_id VARCHAR(255),
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (session_id, chunk_id)
                    )
                ''')
                cursor.execute('''
                    INSERT INTO story_chunks 
                    (session_id, chunk_id, content) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id, chunk_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    created_at = CURRENT_TIMESTAMP
                ''', (session_id, chunk_id, content))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error saving story chunk: {e}")
    
    def get_story_chunk(self, session_id: str, chunk_id: str) -> str:
        """Retrieve story chunk by ID."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
                cursor.execute('''
                    SELECT content FROM story_chunks 
                    WHERE session_id = ? AND chunk_id = ?
                ''', (session_id, chunk_id))
            else:
                cursor.execute('''
                    SELECT content FROM story_chunks 
                    WHERE session_id = %s AND chunk_id = %s
                ''', (session_id, chunk_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0] if self.use_sqlite else result['content']
            return ""
        except Exception as e:
            logging.error(f"Error getting story chunk: {e}")
            return ""
    
    def create_story_summary_db(self, session_id: str, full_content: str, key_points: list) -> str:
        """Create and store intelligent story summaries."""
        try:
            # Extract key sentences based on importance scoring
            sentences = full_content.split('. ')
            important_sentences = []
            
            for sentence in sentences:
                score = 0
                sentence_lower = sentence.lower()
                
                # Score based on key points
                for point in key_points:
                    if point.lower() in sentence_lower:
                        score += 2
                
                # Score tactical content
                if any(word in sentence_lower for word in ["chose", "decided", "attack", "mission", "objective"]):
                    score += 1
                
                if score > 0:
                    important_sentences.append((score, sentence))
            
            # Sort by importance and take top sentences
            important_sentences.sort(key=lambda x: x[0], reverse=True)
            summary_sentences = [s[1] for s in important_sentences[:8]]
            
            # Ensure narrative flow by keeping first and last sentences
            if sentences:
                if sentences[0] not in summary_sentences:
                    summary_sentences = [sentences[0]] + summary_sentences[:7]
                if sentences[-1] not in summary_sentences:
                    summary_sentences = summary_sentences[:7] + [sentences[-1]]
            
            summary = '. '.join(summary_sentences)
            
            # Store the summary
            self.save_story_chunk(session_id, "current_summary", summary)
            
            return summary
        except Exception as e:
            logging.error(f"Error creating story summary: {e}")
            return full_content[:1000]  # Fallback truncation
    
    def get_compressed_story_context(self, session_id: str, max_length: int = 2000) -> str:
        """Get compressed story context for AI generation."""
        try:
            # Get recent story history
            recent_history = self.get_story_history(session_id, limit=3)
            
            # Get stored summary if available
            summary = self.get_story_chunk(session_id, "current_summary")
            
            # Combine summary with recent history
            context_parts = []
            
            if summary:
                context_parts.append(f"Previous events: {summary}")
            
            if recent_history:
                recent_actions = []
                for entry in recent_history[-2:]:  # Last 2 actions
                    if entry['choice']:
                        recent_actions.append(f"Action: {entry['choice']}")
                
                if recent_actions:
                    context_parts.append(f"Recent actions: {' -> '.join(recent_actions)}")
            
            full_context = "\n\n".join(context_parts)
            
            # Truncate if still too long
            if len(full_context) > max_length:
                full_context = full_context[:max_length] + "..."
            
            return full_context
        except Exception as e:
            logging.error(f"Error getting compressed context: {e}")
            return ""
    
    def cleanup_old_sessions(self, days_old: int = 7):
        """Clean up old game sessions."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if self.use_sqlite:
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
            else:
                cursor.execute('''
                    DELETE FROM players 
                    WHERE created_at < NOW() - INTERVAL '%s days'
                ''', (days_old,))
                
                cursor.execute('''
                    DELETE FROM game_sessions 
                    WHERE created_at < NOW() - INTERVAL '%s days'
                ''', (days_old,))
                
                cursor.execute('''
                    DELETE FROM story_history 
                    WHERE created_at < NOW() - INTERVAL '%s days'
                ''', (days_old,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error cleaning up old sessions: {e}")

# Global database instance
db = GameDatabase()
