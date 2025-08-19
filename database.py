'''
Done liao, dont touch
'''


import os
import sqlite3


# ------------------------ Database ------------------------
DB_FILE = "database/recognized_people.db"
os.makedirs("database", exist_ok=True)

def create_recog_db():
    """Initialize the SQLite database and return connection + cursor."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recognized_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            name TEXT,
            counter_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(person_id, name, counter_id)
        )
    ''')
    conn.commit()
    return conn, cursor

def save_recognition(person_id, name, counter_id):
    """Save recognition event into database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO recognized_people (person_id, name, counter_id)
        VALUES (?, ?, ?)
    """, (person_id, name, counter_id))
    conn.commit()
    conn.close()