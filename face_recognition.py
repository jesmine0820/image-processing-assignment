import cv2 as cv
import time
from camera import CameraStream
from fr_insightFace import(
    detector, embeddings_data,smoother,
    get_face_embedding_from_obj, recognize_face, draw_result
)
from fr_mtcnn_facenet import(
    detector_mtcnn, face_database,
    get_top_matches
)

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

def real_time(camera: CameraStream, latest_recognition, counter=1):

    # Parameters for stillness detection
    still_threshold = 20  # max movement in pixels to consider still
    still_duration = 2    # seconds to hold still before capture

    last_face_pos = None
    still_start_time = None
    captured = False
    top_matches = []
    current_person = None
    start_time = None

    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        results = detector_mtcnn.detect_faces(frame)
        person_id, name = None, None

        if len(results) == 0:
            last_face_pos = None
            still_start_time = None
            captured = False
            top_matches = []
            current_person = None
            start_time = None
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
                    (label_width, label_height), baseline = cv.getTextSize(countdown_label, cv.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                    cv.rectangle(frame, (x, y - label_height - baseline - 10), (x + label_width, y), (0, 255, 255), cv.FILLED)
                    cv.putText(frame, countdown_label, (x, y - 5),
                                cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

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
                        
                        # Set recognition results when captured
                        if top_matches:
                            best_name, best_sim = top_matches[0]
                            name = best_name
                            person_id = best_name  # or use a different ID system if available
            else:
                still_start_time = None
                captured = False
                top_matches = []

            last_face_pos = (x, y, w, h)

            if captured and top_matches:
                cv.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                best_name, best_sim = top_matches[0]
                label = f"{best_name} ({best_sim*100:.1f}%)"
                (label_width, label_height), baseline = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv.rectangle(frame, (x, y - label_height - baseline - 5), (x + label_width, y), (0, 255, 0), cv.FILLED)
                cv.putText(frame, label, (x, y - 5), cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                
                # Stable detection logic (similar to the sample)
                if name == current_person:
                    if start_time and (time.time() - start_time >= 5):
                        print(f"Detected: {name}, Score: {best_sim}")
                        start_time = None
                else:
                    current_person = name
                    start_time = time.time()
            else:
                cv.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)

        # Update latest_recognition dictionary
        latest_recognition[counter] = {
            "id": person_id if person_id else "---",
            "name": name if name else "---"
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

        # Yield frame in Flask streaming format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')