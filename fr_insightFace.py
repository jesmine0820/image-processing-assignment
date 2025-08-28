# Import necessary libraries
import cv2 as cv
import pickle
import time
import numpy as np
from insightface.app import FaceAnalysis
from huggingface_hub import hf_hub_download

# Initializer
detector = FaceAnalysis(name="buffalo_l", providers=['CUDAExecutionProvider'])
detector.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.5)

# Load saved embeddings
file_path = hf_hub_download(
    repo_id="jesmine0820/assignment_face_recognition",   
    filename="face_embeddings.pkl",  
    repo_type="dataset"
)
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

def real_time_pipeline():
    current_person = None
    start_time = None

    while True:
        ret, frame = video.read()
        if not ret:
            break

        frame = cv.flip(frame, 1)
        rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

        faces = detector.get(rgb_frame)

        if faces:
            # pick best face (highest det_score)
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
            person_id, name, score = recognize_face(embedding, embeddings_data)

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

        # draw middle guide box
        h, w, _ = frame.shape
        rect_w, rect_h = 200, 200
        center_x, center_y = w // 2, h // 2
        top_left = (center_x - rect_w // 2, center_y - rect_h // 2)
        bottom_right = (center_x + rect_w // 2, center_y + rect_h // 2)
        cv.rectangle(frame, top_left, bottom_right, (255, 0, 0), 2)

        cv.imshow("Face Recognition", frame)
        if cv.waitKey(1) & 0xFF == ord('q'):
            break

    video.release()
    cv.destroyAllWindows()
