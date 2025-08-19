'''
Done liao, dont touch
'''


import cv2 as cv
import pickle
import time
from huggingface_hub import hf_hub_download
from database import save_recognition
from insightFace import(
    detector, preprocess_image, crop_best_face, get_face_embedding_from_obj,
    recognize_face, draw_result, RecognitionSmoother
)

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
def real_time_pipeline(camera):
    # Track recognition time
    current_person = None
    start_time = None

    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                continue  # wait until camera gives frame

            frame = cv.flip(frame, 1)
            h, w, _ = frame.shape 

            faces = detector.get(frame)

            if faces:
                # Crop and preprocess
                processed_img = preprocess_image(frame)
                face_obj = crop_best_face(processed_img)

                if face_obj is not None:
                    if isinstance(face_obj, tuple):
                        face_obj = face_obj[0]

                    if face_obj is not None:
                        try:
                            # Get embedding
                            embedding = get_face_embedding_from_obj(face_obj)

                            # Recognize face
                            person_id, name, score = recognize_face(embedding, embeddings_data)

                            # Smooth results
                            smoother.add_recognition(person_id, score)
                            smoothed_id, smoothed_score = smoother.get_smoothed_result()

                            # Draw results
                            frame = draw_result(frame, name, smoothed_score)

                            # Check for same person for 5s
                            if smoothed_id == current_person:
                                if start_time and (time.time() - start_time >= 5):
                                    save_recognition(person_id, name, "1")
                                    start_time = None
                            else:
                                current_person = smoothed_id
                                start_time = time.time()

                        except Exception as e:
                            print(f"[WARN] Face embedding error: {e}")

            # Draw middle rectangle
            rect_w, rect_h = 200, 200
            center_x, center_y = w // 2, h // 2
            top_left = (center_x - rect_w // 2, center_y - rect_h // 2)
            bottom_right = (center_x + rect_w // 2, center_y + rect_h // 2)
            cv.rectangle(frame, top_left, bottom_right, (255, 0, 0), 2)

            # Convert frame for Flask
            ret, buffer = cv.imencode('.jpg', frame)
            if not ret:
                continue
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        cv.destroyAllWindows()