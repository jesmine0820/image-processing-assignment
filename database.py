import os
import cv2 as cv
import pickle
import sqlite3
from insightface.app import FaceAnalysis
from huggingface_hub import HfApi

# ------------------------ Database ------------------------
DB_FILE = "processed_data/recognized_people.db"
os.makedirs("processed_data", exist_ok=True)

def init_db():
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

# ------------------------ Image Database ------------------------

# Initialize InsightFace with CPU fallback
try:
    app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
except Exception:
    app = FaceAnalysis(providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

def get_file_from_user(folder_path: str) -> str:
    """Validate input folder path."""
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    return folder_path

def process_img(folder_path: str, output_file="face_embeddings.pkl"):
    """Extract embeddings from all images in a folder and save to pickle."""
    embeddings_data = []

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            img_path = os.path.join(folder_path, filename)
            img = cv.imread(img_path)
            if img is None:
                print(f"[WARNING] Could not read {filename}")
                continue

            img_rgb = cv.cvtColor(img, cv.COLOR_BGR2RGB)
            faces = app.get(img_rgb)

            if not faces:
                print(f"[WARNING] No face found in {filename}")
                continue

            face = faces[0]  # Take first face
            embedding = face.normed_embedding
            user_id = os.path.splitext(filename)[0]

            embeddings_data.append({
                'id': user_id,
                'image_name': filename,
                'embedding': embedding
            })

    # Save embeddings
    with open(output_file, "wb") as f:
        pickle.dump(embeddings_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"[INFO] Saved embeddings to {output_file}")
    return output_file

def save_to_hf(file, repo_id="jesmine0820/assignment_face_recognition", hf_token=None):
    """Upload pickle file to HuggingFace Hub dataset repo."""
    api = HfApi(token=hf_token)
    try:
        api.upload_file(
            path_or_fileobj=file,
            path_in_repo=os.path.basename(file),
            repo_id=repo_id,
            repo_type="dataset"
        )
        print(f"[INFO] Uploaded {file} to {repo_id}")
    except Exception as e:
        print(f"[ERROR] Failed to upload {file} to HuggingFace: {e}")
