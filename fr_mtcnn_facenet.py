import cv2
import pickle
import numpy as np
import time
from mtcnn import MTCNN
from keras_facenet import FaceNet
from sklearn.metrics.pairwise import cosine_similarity
from camera import CameraStream

# Initialize detector and embedder
detector = MTCNN()
embedder = FaceNet()

# get the database
with open("database/facenet_embeddings.pkl", "rb") as file:
    face_embeddings = pickle.load(file)

def l2_normalize(x):
    return x / np.linalg.norm(x)

# Get top N matches with cosine similarity
def get_top_matches(face_img, database, top_n=3):
    face_img = cv2.resize(face_img, (160, 160))
    embedding = embedder.embeddings([face_img])[0]
    embedding = l2_normalize(embedding)

    similarities = []
    for name, db_emb in database.items():
        sim_score = cosine_similarity([embedding], [db_emb])[0][0]  # Higher is better
        similarities.append((name, sim_score))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_n]

def real_time(camera: CameraStream, latest_recognition, counter=1):
    # Start webcam recognition with stillness detection
    video = cv2.VideoCapture(0)
    print("📷 Press 'q' to quit...")

    # Parameters for stillness detection
    still_threshold = 10  # max movement in pixels to consider still
    still_duration = 2    # seconds to hold still before capture

    last_face_pos = None
    still_start_time = None
    captured = False
    top_matches = []

    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        results = detector.detect_faces(frame)

        if len(results) == 0:
            last_face_pos = None
            still_start_time = None
            captured = False
            top_matches = []
        else:
            largest_face = max(results, key=lambda f: f['box'][2] * f['box'][3])
            x, y, w, h = largest_face['box']
            x, y = max(0, x), max(0, y)

            if last_face_pos is not None:
                lx, ly, lw, lh = last_face_pos
                movement = abs(x - lx) + abs(y - ly) + abs(w - lw) + abs(h - lh)
            else:
                movement = None

            if movement is not None and movement < still_threshold:
                if still_start_time is None:
                    still_start_time = time.time()
                else:
                    elapsed = time.time() - still_start_time
                    remaining = int(still_duration - elapsed) + 1

                    countdown_label = f"Hold still... {remaining}s"
                    (label_width, label_height), baseline = cv2.getTextSize(countdown_label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                    cv2.rectangle(frame, (x, y - label_height - baseline - 10), (x + label_width, y), (0, 255, 255), cv2.FILLED)
                    cv2.putText(frame, countdown_label, (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

                    if elapsed >= still_duration and not captured:
                        margin = 10
                        x1 = max(0, x - margin)
                        y1 = max(0, y - margin)
                        x2 = min(frame.shape[1], x + w + margin)
                        y2 = min(frame.shape[0], y + h + margin)
                        face_img = frame[y1:y2, x1:x2]

                        top_matches = get_top_matches(face_img, face_database)

                        print(f"\nCaptured face after being still for {still_duration} seconds:")
                        for match_name, sim in top_matches:
                            print(f"  {match_name}: {sim * 100:.2f}% similarity")

                        captured = True
            else:
                still_start_time = None
                captured = False
                top_matches = []

            last_face_pos = (x, y, w, h)

            if captured and top_matches:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                best_name, best_sim = top_matches[0]
                label = f"{best_name} ({best_sim*100:.1f}%)"
                (label_width, label_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(frame, (x, y - label_height - baseline - 5), (x + label_width, y), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            else:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)

        # Encode frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        # Yield frame in Flask streaming format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')