# Import necessary libraries
import cv2 as cv
import pickle
import numpy as np
import pandas as pd
import time
from insightface.app import FaceAnalysis
from mtcnn import MTCNN
from keras_facenet import FaceNet
from sklearn.metrics.pairwise import cosine_similarity

from camera import CameraStream

# Initializer
detector_if = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
detector_if.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.5)
df = pd.read_csv("dataset/dataset.csv")
id_to_name = dict(zip(df["StudentID"], df["Name"]))

# --------------- InsightFace ---------------

# Load saved embeddings
file_path = "database/face_embeddings.pkl"
with open(file_path, "rb") as f:
    embeddings_data = pickle.load(f)

# Smoother Class
class RecognitionSmoother:
    def __init__(self, window_size=5):
        self.window_size = window_size
        self.history = []
    
    def add_recognition(self, person_id, score):
        self.history.append((person_id, score))
        if len(self.history) > self.window_size:
            self.history.pop(0)
    
    def get_smoothed_result(self):
        if not self.history:
            return None, 0

        weights = np.linspace(0.5, 1.5, len(self.history))
        scores = {}
        
        for (pid, score), weight in zip(self.history, weights):
            if pid not in scores:
                scores[pid] = []
            scores[pid].append(score * weight)
        
        avg_scores = {pid: np.mean(vals) for pid, vals in scores.items()}
        best_pid = max(avg_scores.items(), key=lambda x: x[1])[0]
        best_score = avg_scores[best_pid]
        
        return best_pid, best_score
    
# Initialize smoother
smoother = RecognitionSmoother(window_size=5)

# Initialize camera
video = cv.VideoCapture(0)

# Detect the brightness
# Get embeddings
def get_face_embedding_from_obj(face_obj):
    emb = face_obj.embedding
    if emb is None:
        return None
    return emb / np.linalg.norm(emb)

# Use Cosine similarity
def recognize_face(embedding, dataset, threshold=0.5):
    if embedding is None:
        return None, None, -1

    best_score = -1
    best_id = None
    best_name = None

    for entry in dataset:
        db_embedding = entry["embedding"]
        db_embedding = db_embedding / np.linalg.norm(db_embedding)

        cos_sim = np.dot(embedding, db_embedding)
        if cos_sim > best_score:
            best_score = cos_sim
            best_id = entry["id"]
            best_name = entry["image_name"]

    if best_score < threshold:
        return None, None, best_score

    return best_id, best_name, best_score

# Draw rectangle on the face
def draw_result(image, name, score):
    faces = detector_if.get(image)
    if not faces:
        return image

    h, w, _ = image.shape
    img_center = np.array([w // 2, h // 2])
    closest_face, min_dist = None, float("inf")

    for face in faces:
        bbox = face.bbox.astype(int)
        face_center = np.array([(bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2])
        dist = np.linalg.norm(face_center - img_center)
        if dist < min_dist:
            min_dist = dist
            closest_face = face

    if closest_face is None:
        return image

    bbox = closest_face.bbox.astype(int)
    cv.rectangle(image, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)

    label = f"{name} ({score:.2f})" if name else "Unknown"
    cv.putText(image, label, (bbox[0], bbox[1] - 10),
               cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return image

def real_time_pipeline(camera: CameraStream, latest_recognition, counter=1):
    current_person = None
    start_time = None

    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        person_id, name = None, None

        frame = cv.flip(frame, 1)
        rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

        faces = detector_if.get(rgb_frame)

        if faces:
            # pick best face
            faces.sort(key=lambda f: f.det_score, reverse=True)
            best_face = faces[0]

            # face quality filtering
            if best_face.det_score < 0.6:
                continue
            if (best_face.bbox[2] - best_face.bbox[0]) < 80:
                continue

            # get embedding
            embedding = get_face_embedding_from_obj(best_face)

            # recognize
            person_id, pred_name, score = recognize_face(embedding, embeddings_data)

            if person_id in id_to_name:
                name = id_to_name[person_id]
            else:
                name = pred_name

            # smooth results
            smoother.add_recognition(person_id, score)
            smoothed_id, smoothed_score = smoother.get_smoothed_result()

            # draw
            frame = draw_result(frame, name, smoothed_score)

            # stable detection for 5s
            if smoothed_id == current_person:
                if start_time and (time.time() - start_time >= 5):
                    print(f"Detected id: {smoothed_id}, Score: {smoothed_score}")
                    start_time = None
            else:
                current_person = smoothed_id
                start_time = time.time()

        latest_recognition[counter] = {
            "id": person_id if person_id else "---",
            "name": name if name else "---"
        }

        # draw middle guide box
        h, w, _ = frame.shape
        rect_w, rect_h = 200, 200
        center_x, center_y = w // 2, h // 2
        top_left = (center_x - rect_w // 2, center_y - rect_h // 2)
        bottom_right = (center_x + rect_w // 2, center_y + rect_h // 2)
        cv.rectangle(frame, top_left, bottom_right, (255, 0, 0), 2)

        # Encode frame as JPEG
        ret, jpeg = cv.imencode('.jpg', frame)
        if not ret:
            continue

        # Yield frame in Flask streaming format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        
# --------------- MTCNN + FaceNet ---------------
# Initialize detector and embedder
detector_mtcnn = MTCNN()
embedder = FaceNet()

# get the database
with open("database/facenet_embeddings.pkl", "rb") as file:
    face_database = pickle.load(file)

def l2_normalize(x):
    return x / np.linalg.norm(x)

# Get top N matches with cosine similarity
def get_top_matches(face_img, database, top_n=3):
    face_img = cv.resize(face_img, (160, 160))
    embedding = embedder.embeddings([face_img])[0]
    embedding = l2_normalize(embedding)

    similarities = []
    for name, db_emb in database.items():
        sim_score = cosine_similarity([embedding], [db_emb])[0][0]  # Higher is better
        similarities.append((name, sim_score))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_n]

def real_time(camera: CameraStream, latest_recognition_scan, counter=1):

    # Parameters for stillness detection
    still_threshold = 35   # max movement in pixels to consider still
    still_duration = 2     # seconds to hold still before capture

    last_face_pos = None
    still_start_time = None
    captured = False
    top_matches = []
    current_person = None
    start_time = None

    # store last valid recognition
    last_valid_id, last_valid_name = None, None

    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        results = detector_mtcnn.detect_faces(frame)
        person_id, name = None, None

        if len(results) == 0:
            # if no face detected → keep last valid instead of resetting
            person_id, name = last_valid_id, last_valid_name
            last_face_pos = None
            still_start_time = None
            captured = False
            top_matches = []
            current_person = None
            start_time = None

        else:
            # pick largest face
            largest_face = max(results, key=lambda f: f['box'][2] * f['box'][3])
            x, y, w, h = largest_face['box']
            x, y = max(0, x), max(0, y)

            # measure movement
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
                    (label_width, label_height), baseline = cv.getTextSize(
                        countdown_label, cv.FONT_HERSHEY_SIMPLEX, 0.8, 2
                    )
                    cv.rectangle(frame, (x, y - label_height - baseline - 10),
                                 (x + label_width, y), (0, 255, 255), cv.FILLED)
                    cv.putText(frame, countdown_label, (x, y - 5),
                               cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

                    # capture face after stillness
                    if elapsed >= still_duration and not captured:
                        margin = 10
                        x1 = max(0, x - margin)
                        y1 = max(0, y - margin)
                        x2 = min(frame.shape[1], x + w + margin)
                        y2 = min(frame.shape[0], y + h + margin)
                        face_img = frame[y1:y2, x1:x2]

                        top_matches = get_top_matches(face_img, face_database)
                        captured = True

                        if top_matches:
                            best_id, best_sim = top_matches[0]
                            person_id = best_id
                            name = id_to_name.get(best_id, best_id)

                            # update last valid recognition
                            last_valid_id, last_valid_name = person_id, name

                            print(f"\nCaptured face: {name} ({best_sim*100:.2f}% similarity)")

            else:
                still_start_time = None
                captured = False
                top_matches = []

            last_face_pos = (x, y, w, h)

            if captured and top_matches:
                cv.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                best_id, best_sim = top_matches[0]
                label = f"{id_to_name.get(best_id, best_id)} ({best_sim*100:.1f}%)"
                (label_width, label_height), baseline = cv.getTextSize(
                    label, cv.FONT_HERSHEY_SIMPLEX, 0.7, 2
                )
                cv.rectangle(frame, (x, y - label_height - baseline - 5),
                             (x + label_width, y), (0, 255, 0), cv.FILLED)
                cv.putText(frame, label, (x, y - 5),
                           cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

                # Stable detection logic (5s)
                if name == current_person:
                    if start_time and (time.time() - start_time >= 5):
                        print(f"Stable detection: {name}, Score: {best_sim}")
                        start_time = None
                else:
                    current_person = name
                    start_time = time.time()
            else:
                # show yellow box if no valid capture
                cv.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)

        # always push last known recognition (not reset to "---")
        latest_recognition_scan[counter] = {
            "id": last_valid_id if last_valid_id else "---",
            "name": last_valid_name if last_valid_name else "---"
        }

        # Draw middle guide box
        h, w, _ = frame.shape
        rect_w, rect_h = 200, 200
        center_x, center_y = w // 2, h // 2
        top_left = (center_x - rect_w // 2, center_y - rect_h // 2)
        bottom_right = (center_x + rect_w // 2, center_y + rect_h // 2)
        cv.rectangle(frame, top_left, bottom_right, (255, 0, 0), 2)

        # Encode frame as JPEG
        ret, jpeg = cv.imencode('.jpg', frame)
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
