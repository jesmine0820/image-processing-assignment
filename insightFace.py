import cv2 as cv
import numpy as np
from insightface.app import FaceAnalysis
from huggingface_hub import hf_hub_download

# Initialize face detector
detector = FaceAnalysis(name="buffalo_l", providers=['CUDAExecutionProvider'])
detector.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.5)

# Initializer
target_size = (224,244)
threshold = 0.5
window_size = 5

# Declare smoother for recognition result
class RecognitionSmoother:
    def __init__(self, window_size=window_size):
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

# Detect the brightness
def detect_brightness(image):
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    return np.mean(gray)

# Adjust gamma
def adjust_gamma(image, gamma):
    inv_gamma = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv_gamma * 255 for i in np.arange(256)]).astype("uint8")
    return cv.LUT(image, table)

def preprocess_image(img, target_size=target_size):

    # Gamma correction based on brightness
    brightness = detect_brightness(img)
    if brightness > 180:
        img = adjust_gamma(img, gamma=1.5)
    elif brightness < 70:
        img = adjust_gamma(img, gamma=0.5)
        
    # Normalize and resize
    img_rgb = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    img_resized = cv.resize(img_rgb, target_size, interpolation=cv.INTER_AREA)
    
    # Smart blurring
    if cv.Laplacian(img_resized, cv.CV_64F).var() < 100:
        img_resized = cv.GaussianBlur(img_resized, (3, 3), 0)
    
    return img_resized

def crop_best_face(image):
    faces = detector.get(image)
    if not faces:
        return None, None

    img_h, img_w = image.shape[:2]
    img_center = np.array([img_w / 2, img_h / 2])

    scored_faces = []
    for face in faces:
        bbox = face.bbox.astype(int)

        # Clamp bounding box inside image
        x1, y1 = max(0, bbox[0]), max(0, bbox[1])
        x2, y2 = min(img_w, bbox[2]), min(img_h, bbox[3])
        if x2 <= x1 or y2 <= y1:
            continue

        # Center proximity score
        face_center = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
        center_score = 1 - (np.linalg.norm(face_center - img_center) /
                            np.linalg.norm(img_center))

        # Face size score
        face_area = (x2 - x1) * (y2 - y1)
        size_score = face_area / (img_w * img_h)

        # Detection confidence
        det_score = face.det_score if hasattr(face, "det_score") else 0.5

        # Sharpness score
        face_roi = image[y1:y2, x1:x2]
        sharpness_score = 0
        if face_roi.size > 0:
            gray_face = cv.cvtColor(face_roi, cv.COLOR_BGR2GRAY)
            sharpness = cv.Laplacian(gray_face, cv.CV_64F).var()
            sharpness_score = min(sharpness / 1000, 1.0)  # normalize

        # Weighted total score
        total_score = (0.4 * center_score +
                       0.3 * size_score +
                       0.2 * det_score +
                       0.1 * sharpness_score)

        scored_faces.append((total_score, (x1, y1, x2, y2), face))

    if not scored_faces:
        return None, None

    # Pick best face
    scored_faces.sort(reverse=True, key=lambda x: x[0])
    _, (x1, y1, x2, y2), best_face = scored_faces[0]

    return best_face

def get_face_embedding_from_obj(face_obj):
    return face_obj.embedding

def recognize_face(embedding, dataset):
    best_score = -1
    best_id = None
    best_name = None
    
    for entry in dataset:
        db_embedding = entry["embedding"]
        
        # Cosine similarity
        cos_sim = np.dot(embedding, db_embedding) / (
            np.linalg.norm(embedding) * np.linalg.norm(db_embedding)
        )
        
        # Euclidean distance 
        eucl_dist = np.linalg.norm(embedding - db_embedding)
        eucl_sim = 1 / (1 + eucl_dist) 
        
        # Combined score 
        similarity = 0.7 * cos_sim + 0.3 * eucl_sim
        
        if similarity > best_score:
            best_score = similarity
            best_id = entry["id"]
            best_name = entry["image_name"]
    
    return best_id, best_name, best_score

def draw_result(image, name, score):
    faces = detector.get(image)

    if not faces:
        return image

    # Image center
    h, w, _ = image.shape
    img_center = np.array([w // 2, h // 2])

    # Find face closest to center
    closest_face = None
    min_dist = float('inf')

    for face in faces:
        bbox = face.bbox.astype(int)
        face_center = np.array([(bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2])
        dist = np.linalg.norm(face_center - img_center)

        if dist < min_dist:
            min_dist = dist
            closest_face = face

    if closest_face is None:
        return image

    # Get bounding box for closest face
    bbox = closest_face.bbox.astype(int)

    # Draw rectangle
    cv.rectangle(image, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)

    # Create label
    label = f"{name} ({score:.2f})"
    cv.putText(image, label, (bbox[0], bbox[1] - 10),
               cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return image
