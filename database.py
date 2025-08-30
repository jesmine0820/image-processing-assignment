import os
import sqlite3
import barcode
import pandas as pd
from barcode.writer import ImageWriter
from huggingface_hub import Repository

def generate_and_push_barcodes(
    dataset_path="dataset/dataset.csv",
    repo_id="jesmine0820/assignment-barcode-generated",
    local_dir="temp_barcode_repo"
):
    
    # Load dataset
    df = pd.read_csv(dataset_path)

    # Local directory
    os.makedirs(local_dir, exist_ok=True)

    # Barcode class
    Code128 = barcode.get_barcode_class("code128")

    count = 0
    for idx, student in df.iterrows():
        student_id = str(student["StudentID"])
        name = student["Name"].replace(" ", "_")

        # Instantiate the barcode with data
        code128 = Code128(student_id, writer=ImageWriter())

        # Save barcode PNG into repo folder
        filename = os.path.join(local_dir, f"{student_id}_{name}")
        code128.save(filename)
        count += 1

    # --- Push to Hugging Face Hub ---
    repo = Repository(local_dir, clone_from=repo_id, use_auth_token=True)
    repo.push_to_hub(commit_message=f"Added {count} barcodes")

# ------------------------ Database ------------------------
DB_FILE = "database/recognized_people.db"
os.makedirs("database", exist_ok=True)

def create_recog_db():
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO recognized_people (person_id, name, counter_id)
        VALUES (?, ?, ?)
    """, (person_id, name, counter_id))
    conn.commit()
    conn.close()