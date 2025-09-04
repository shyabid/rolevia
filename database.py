import sqlite3
import json
import asyncio
from typing import Optional, List, Dict, Any
import threading

class Database:
    def __init__(self, db_path: str = "rolevia.db"):
        self.db_path = db_path
        self.local = threading.local()
        self.init_db()
    
    def get_connection(self):
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                questions TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                passing_percentage INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER,
                webhook_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                passed BOOLEAN NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES quiz_data (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_messages (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES quiz_data (id)
            )
        ''')
        
        conn.commit()
    
    def save_quiz(self, guild_id: int, questions: List[Dict], role_id: int, passing_percentage: int) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO quiz_data (guild_id, questions, role_id, passing_percentage)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, json.dumps(questions), role_id, passing_percentage))
        
        quiz_id = cursor.lastrowid
        conn.commit()
        return quiz_id
    
    def get_quiz(self, quiz_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM quiz_data WHERE id = ?
        ''', (quiz_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row['id'],
                'guild_id': row['guild_id'],
                'questions': json.loads(row['questions']),
                'role_id': row['role_id'],
                'passing_percentage': row['passing_percentage'],
                'created_at': row['created_at']
            }
        return None
    
    def set_log_channel(self, guild_id: int, channel_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO guild_settings (guild_id, log_channel_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (guild_id, channel_id))
        
        conn.commit()
    
    def get_log_channel(self, guild_id: int) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT log_channel_id FROM guild_settings WHERE guild_id = ?
        ''', (guild_id,))
        
        row = cursor.fetchone()
        return row['log_channel_id'] if row and row['log_channel_id'] else None
    
    def set_webhook_url(self, guild_id: int, webhook_url: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO guild_settings (guild_id, webhook_url, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (guild_id, webhook_url))
        
        conn.commit()
    
    def get_webhook_url(self, guild_id: int) -> Optional[str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT webhook_url FROM guild_settings WHERE guild_id = ?
        ''', (guild_id,))
        
        row = cursor.fetchone()
        return row['webhook_url'] if row and row['webhook_url'] else None
    
    def log_quiz_attempt(self, guild_id: int, user_id: int, quiz_id: int, score: int, total_questions: int, passed: bool):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO quiz_logs (guild_id, user_id, quiz_id, score, total_questions, passed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guild_id, user_id, quiz_id, score, total_questions, passed))
        
        conn.commit()
    
    def get_quiz_logs(self, guild_id: int, limit: int = 50) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM quiz_logs 
            WHERE guild_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (guild_id, limit))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def save_quiz_message(self, message_id: int, channel_id: int, guild_id: int, quiz_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO quiz_messages (message_id, channel_id, guild_id, quiz_id)
            VALUES (?, ?, ?, ?)
        ''', (message_id, channel_id, guild_id, quiz_id))
        
        conn.commit()
    
    def get_quiz_from_message(self, message_id: int) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT quiz_id FROM quiz_messages WHERE message_id = ?
        ''', (message_id,))
        
        row = cursor.fetchone()
        return row['quiz_id'] if row else None

# Global database instance
db = Database()
