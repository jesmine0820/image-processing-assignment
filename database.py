import os
import sqlite3
import barcode
import pandas as pd
from barcode.writer import ImageWriter

# ------------------------ Generate BarCode Data ------------------------
def generate_barcodes(
    dataset_path="dataset/dataset.csv",
    output_dir="database/barcode_generated"
):
    # Load dataset
    df = pd.read_csv(dataset_path)

    # Create output directory if not exists
    os.makedirs(output_dir, exist_ok=True)

    # Barcode class
    Code128 = barcode.get_barcode_class("code128")

    count = 0
    for idx, student in df.iterrows():
        student_id = str(student["StudentID"])
        name = student["Name"].replace(" ", "_")

        # Generate barcode
        code128 = Code128(student_id, writer=ImageWriter())

        # Save barcode PNG into output folder
        filename = os.path.join(output_dir, f"{student_id}_{name}")
        code128.save(filename)
        count += 1
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