import cv2 as cv
import numpy as np
import os
import pickle
import time
from huggingface_hub import hf_hub_download
from database import init_db, save_recognition
from insightFace import(
    detector, preprocess_image, crop_best_face, get_face_embedding_from_obj,
    recognize_face, draw_result, RecognitionSmoother
)

# Initialize database
conn, cursor = init_db()

# Load dataset
file_path = hf_hub_download(
    repo_id="jesmine0820/assignment_face_recognition",   
    filename="face_embeddings.pkl",  
    repo_type="dataset"
)
with open(file_path, "rb") as f:
    embeddings_data = pickle.load(f)

# Initialize recognition smoother
smoother = RecognitionSmoother(window_size=5)

# InsightFace 
def real_time_pipeline():
    # Open webcam
    video = cv.VideoCapture(0)

    # Track recognition time
    current_person = None
    start_time = None
    saved_people = set()

    save_file = "processed_data/recognized_people.txt"
    if os.path.exists(save_file):
        with open(save_file, "r") as file:
            saved_people = set(line.strip() for line in file.readlines())

    while True:
        ret, frame = video.read()
        if not ret:
            break

        frame = cv.flip(frame, 1)

        # Detect faces with buffalo_l
        faces = detector.get(frame)

        if faces:
            # Find face closest to center
            h, w, _ = frame.shape
            img_center = np.array([w // 2, h // 2])
            closest_face = min(
                faces,
                key=lambda f: np.linalg.norm(
                    np.array([(f.bbox[0] + f.bbox[2]) / 2, (f.bbox[1] + f.bbox[3]) / 2]) - img_center
                )
            )

            # Crop and preprocess
            processed_img = preprocess_image(frame)
            cropped_face, face_obj = crop_best_face(processed_img)

            if face_obj is not None:
                # Get embedding
                embedding = get_face_embedding_from_obj(face_obj)

                # Recognize face
                person_id, name, score = recognize_face(embedding, embeddings_data)

                # Smooth results
                smoother.add_recognition(person_id, score)
                smoothed_id, smoothed_score = smoother.get_smoothed_result()

                # Draw results
                frame = draw_result(frame, name, smoothed_score)

                # Print info
                print(f"Detect id: {person_id}, Score: {score:.2f}")

                # Check for same people
                if smoothed_id == current_person:
                    if start_time and (time.time() - start_time >= 5):
                        save_recognition(person_id, name, "1")
                        start_time = None
                else:
                    current_person = smoothed_id
                    start_time = time.time()

        # Draw middle rectangle
        rect_w, rect_h = 200, 200
        center_x, center_y = w // 2, h // 2
        top_left = (center_x - rect_w // 2, center_y - rect_h // 2)
        bottom_right = (center_x + rect_w // 2, center_y + rect_h // 2)
        cv.rectangle(frame, top_left, bottom_right, (255, 0, 0), 2)

        # Convert frame for Flask
        ret, buffer = cv.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    video.release()
