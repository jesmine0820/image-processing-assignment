import time
import cv2 as cv
import torch
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

def draw_box_with_label(img, tlbr, label, color=(0, 255, 0)):
    x1, y1, x2, y2 = map(int, tlbr)
    cv.rectangle(img, (x1, y1), (x2, y2), color, 2)
    (tw, th), _ = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv.rectangle(img, (x1, y1 - th - 6), (x1 + tw + 6, y1), color, -1)
    cv.putText(img, label, (x1 + 3, y1 - 6),
                cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
def track_person(model_path="yolov8n.pt", threshold=0.4, camera_index=0):
    # Load YOLO
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = YOLO(model_path)
    model.to(device)

    # DeepSORT tracker
    tracker = DeepSort(
        max_age=30,
        n_init=3,
        max_iou_distance=0.7,
        nms_max_overlap=1.0,
        max_cosine_distance=0.2,
        nn_budget=None,
        embedder="mobilenet",
        half=torch.cuda.is_available(),
        bgr=True,
    )
    
    # Init video
    video = cv.VideoCapture(camera_index)
    fps_smooth = None
    person_class_id = 0  # YOLO class for "person"

    # Accuracy tracking
    prev_ids = {}
    id_switches = 0
    total_tracks = 0

    # Right-to-left detection
    track_positions = {}  # track_id → [first_x, last_x]

    while True:
        ret, frame = video.read()
        if not ret:
            break

        frame = cv.flip(frame, 1)
        t0 = time.time()
        h, w, _ = frame.shape

        # Detect people (full body)
        results = model.predict(frame, conf=threshold, iou=0.45,
                                verbose=False, classes=[person_class_id], device=device)

        detections = []
        if len(results):
            r = results[0]
            if r.boxes is not None and len(r.boxes) > 0:
                for box in r.boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())

                    # Ensure full body bounding box 
                    x1, y1, x2, y2 = xyxy
                    x1 = max(0, int(x1))
                    y1 = max(0, int(y1))
                    x2 = min(w, int(x2))
                    y2 = min(h, int(y2))
                    detections.append([[x1, y1, x2, y2], conf, "person"])

        # Update tracker
        tracks = tracker.update_tracks(detections, frame=frame)

        for trk in tracks:
            if not trk.is_confirmed() or trk.time_since_update > 0:
                continue
            track_id = trk.track_id
            tlbr = trk.to_tlbr()
            x1, y1, x2, y2 = map(int, tlbr)
            cx = (x1 + x2) // 2  # center x

            # Draw
            draw_box_with_label(frame, tlbr, f"ID {track_id}")

            # Accuracy check 
            total_tracks += 1
            if track_id in prev_ids:
                if prev_ids[track_id] != track_id:
                    id_switches += 1
            prev_ids[track_id] = track_id

            # Movement Right -> Left 
            if track_id not in track_positions:
                track_positions[track_id] = [cx, cx]  
            else:
                track_positions[track_id][1] = cx 

                start_x, last_x = track_positions[track_id]

                if start_x > 0.7 * w and last_x < 0.3 * w:
                    print("Next person")
                    track_positions.pop(track_id)

        # FPS
        dt = time.time() - t0
        fps = 1.0 / dt if dt > 0 else 0.0
        fps_smooth = fps if fps_smooth is None else fps_smooth * 0.9 + fps * 0.1
        cv.putText(frame, f"FPS: {fps_smooth:.1f}", (10, 30),
                   cv.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Accuracy display
        if total_tracks > 0:
            accuracy = 1 - (id_switches / total_tracks)
            cv.putText(frame, f"Accuracy: {accuracy:.2f}", (10, 60),
                       cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        ok, buf = cv.imencode(".jpg", frame)
        if not ok:
            continue

        yield (b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
