# Import necessary libraries
import cv2 as cv
import pickle
import numpy as np
from insightface.app import FaceAnalysis

# Initializer
detector = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
detector.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.5)

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
    faces = detector.get(image)
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

