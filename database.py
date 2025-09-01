import os
import sqlite3

# Initializer
DB_FILE = "database/recognized_people.db"
os.makedirs("database", exist_ok=True)

# --- Recognitized Person Database ---
def create_recog_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recognized_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            name TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            queue_timestamp DATETIME,
            queue TEXT,
            UNIQUE(person_id, name)
        )
    ''')
    conn.commit()
    return conn, cursor

def save_recognition(person_id, name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO recognized_people (person_id, name)
        VALUES (?, ?)
    """, (person_id, name))
    conn.commit()
    conn.close()