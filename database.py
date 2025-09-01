import os
import sqlite3

# Initializer
DB_FILE = "database/recognized_people.db"
os.makedirs("database", exist_ok=True)

# --- Recognitized Person Database ---
def clear_database():
    """Clear all data from the database on startup"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recognized_people")
    conn.commit()
    conn.close()
    print("[INFO] Database cleared on startup")

def create_recog_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recognized_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            name TEXT,
            attendance TEXT DEFAULT 'N',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            queue_timestamp DATETIME,
            queue TEXT,
            UNIQUE(person_id, name)
        )
    ''')
    conn.commit()

    # Ensure attendance column exists for older DBs
    cursor.execute("PRAGMA table_info(recognized_people)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'attendance' not in cols:
        cursor.execute("ALTER TABLE recognized_people ADD COLUMN attendance TEXT DEFAULT 'N'")
        conn.commit()

    conn.close()
    
    # Clear database on startup
    clear_database()
    
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

def set_attendance(person_id: str, status: str = 'Y'):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE recognized_people
        SET attendance = ?
        WHERE person_id = ?
    """, (status, person_id))
    # If no row updated, insert
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO recognized_people (person_id, name, attendance)
            VALUES (?, ?, ?)
        """, (person_id, person_id, status))
    conn.commit()
    conn.close()

def has_attendance_yes(person_id: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT attendance FROM recognized_people WHERE person_id = ?", (person_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row and (row[0] or '').upper() == 'Y')