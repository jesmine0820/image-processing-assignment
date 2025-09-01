import pandas as pd
import barcode
import os
import cv2 as cv
import time
import qrcode
import zxingcpp
import numpy as np
import re
from pyzbar import pyzbar
from ultralytics import YOLO
from barcode.writer import ImageWriter

from utility import graduation_level
from camera import CameraStream

# Initializer
df = pd.read_csv("dataset/dataset.csv")
generate_output_dir = "database/barcode_generated"
student_dict = df.set_index("StudentID").to_dict("index")

# --- Generate barcode data ---
def generate_barcodes():
    # Initialize barcode
    Code128 = barcode.get_barcode_class("code128")
    count = 0
    for idx, student in df.iterrows():
        student_id = str(student["StudentID"])
        name = student["Name"].replace(" ", "_")

        # Generate barcode
        code128 = Code128(student_id, writer=ImageWriter())

        # Save barcode
        filename = os.path.join(generate_output_dir, f"{student_id}_{name}")
        code128.save(filename)
        count += 1

# ----------ZXingCpp----------
def scan_barcode_generator(camera: CameraStream, latest_scan_result):
    target_w, target_h = 402, 280
    
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        h, w, _ = frame.shape
        roi_w = int(w * target_w / w)
        roi_h = int(h * target_h / h)
        roi_x1 = w//2 - roi_w//2
        roi_y1 = h//2 - roi_h//2
        roi_x2 = roi_x1 + roi_w
        roi_y2 = roi_y1 + roi_h

        # Semi-transparent overlay
        overlay = frame.copy()
        overlay[:] = (0,0,0)
        frame = cv.addWeighted(overlay, 0.6, frame, 0.4, 0)
        
        # Get fresh frame for ROI
        raw_frame = camera.get_frame()
        if raw_frame is not None:
            frame[roi_y1:roi_y2, roi_x1:roi_x2] = raw_frame[roi_y1:roi_y2, roi_x1:roi_x2]

        # Decode barcode in ROI
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
        results = zxingcpp.read_barcodes(gray)

        display_name = "Awaiting scan..."
        display_id = ""
        valid_student = False

        if results:
            student_id = results[0].text.strip()
            if student_id in student_dict:
                info = student_dict[student_id]
                display_name = info['Name']
                display_id = student_id
                valid_student = True
                if isinstance(latest_scan_result, dict):
                    latest_scan_result.clear()
                    latest_scan_result.update({
                        "type": "barcode",
                        "data": student_id,
                        "info": info
                    })
            else:
                display_name = "INVALID BARCODE"
                display_id = ""
                valid_student = False

        # Display text and ROI
        cv.putText(frame, f"Name: {display_name}", (roi_x1, roi_y2+30),
                    cv.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0) if valid_student else (0,0,255),2)
        cv.putText(frame, f"ID: {display_id}", (roi_x1, roi_y2+70),
                    cv.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0) if valid_student else (0,0,255),2)
        cv.rectangle(frame, (roi_x1, roi_y1), (roi_x2, roi_y2), (255,0,0),3)
        
        # Encode frame for streaming
        ret, buffer = cv.imencode('.jpg', frame)
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # If encoding fails, yield an empty frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')

def generate_qr_code(student_id, info):
    level = graduation_level(info["CGPA"])
    qr_data = f"ID:{student_id}\nName:{info['Name']}\nFaculty:{info['Faculty']}\nGraduation Level:{level}"

    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    os.makedirs("database/QR_codes", exist_ok=True)
    qr_path = f"database/QR_codes/{student_id}.png"
    qr_img.save(qr_path)
    print(f"QR code saved: {qr_path}")
    
    return qr_path

def scan_qr_code_generator(camera: CameraStream, latest_scan_result):
    target_w, target_h = 402, 280

    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        h, w, _ = frame.shape
        roi_w = int(w * target_w / w)
        roi_h = int(h * target_h / h)
        roi_x1 = w//2 - roi_w//2
        roi_y1 = h//2 - roi_h//2
        roi_x2 = roi_x1 + roi_w
        roi_y2 = roi_y1 + roi_h

        overlay = frame.copy()
        overlay[:] = (0,0,0)
        frame = cv.addWeighted(overlay, 0.6, frame, 0.4, 0)
        
        # Get fresh frame for ROI
        raw_frame = camera.get_frame()
        if raw_frame is not None:
            frame[roi_y1:roi_y2, roi_x1:roi_x2] = raw_frame[roi_y1:roi_y2, roi_x1:roi_x2]

        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
        results = zxingcpp.read_barcodes(gray)

        if results:
            qr_data = results[0].text.strip()
            if "ID:" in qr_data:
                student_id = qr_data.split("ID:")[1].split("\n")[0].strip()
                if student_id in student_dict:
                    info = student_dict[student_id]
                    if isinstance(latest_scan_result, dict):
                        latest_scan_result.clear()
                        latest_scan_result.update({
                            "type": "qrcode",
                            "data": student_id,
                            "info": info
                        })
                    
                    # Display success message
                    cv.putText(frame, "QR CODE SCANNED SUCCESSFULLY", (50, 50),
                              cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Encode frame for streaming
        ret, buffer = cv.imencode('.jpg', frame)
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # If encoding fails, yield an empty frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')

# ----------PyZBar----------
def safe_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", s)

def parse_qr_text(qr_text: str) -> dict:
    info = {}
    for line in str(qr_text).splitlines():
        m = re.match(r"\s*([^:]+)\s*:\s*(.*)\s*$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            info[key] = val
    return info

def scan_barcode_py_generator(camera: CameraStream, latest_scan_result):
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)

        for bc in barcodes:
            sid = bc.data.decode("utf-8").strip()
            if sid in student_dict:
                info = student_dict[sid]
                if isinstance(latest_scan_result, dict):
                    latest_scan_result.clear()
                    latest_scan_result.update({
                        "type": "barcode",
                        "data": sid,
                        "info": info
                    })
                
                # Draw bounding box and info
                (x, y, w, h) = bc.rect
                cv.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv.putText(frame, f"ID: {sid}", (x, y - 10),
                          cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Encode frame for streaming
        ret, buffer = cv.imencode('.jpg', frame)
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # If encoding fails, yield an empty frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')

def generate_qr_py(student_id, info, qr_folder="qrcodes"):
    os.makedirs(qr_folder, exist_ok=True)
    qr_file = os.path.join(qr_folder, f"{student_id}_{safe_filename(info['Name'])}.png")
    content = (
        f"Name: {info['Name']}\n"
        f"StudentID: {info['StudentID']}\n"
        f"Faculty: {info['Faculty']}\n"
        f"Course: {info['Course']}\n"
        f"CGPA: {info['CGPA']}"
    )
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(content)
    qr.make(fit=True)
    qr.make_image(fill="black", back_color="white").save(qr_file)
    print(f"QR generated: {qr_file}")
    return qr_file

def scan_qr_code_generator(camera: CameraStream, latest_scan_result):
    detector = cv.QRCodeDetector()

    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        data, points, _ = detector.detectAndDecode(frame)
        if data:
            info = parse_qr_text(data)
            sid = str(info.get("StudentID", "")).strip()
            if sid in student_dict:
                info = student_dict[sid]
                if isinstance(latest_scan_result, dict):
                    latest_scan_result.clear()
                    latest_scan_result.update({
                        "type": "qrcode",
                        "data": sid,
                        "info": info
                    })
                
                # Draw bounding box
                if points is not None:
                    points = points[0].astype(int)
                    for i in range(len(points)):
                        cv.line(frame, tuple(points[i]), tuple(points[(i+1) % len(points)]), (0, 255, 0), 3)
                
                cv.putText(frame, "QR CODE DETECTED", (50, 50),
                          cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Encode frame for streaming
        ret, buffer = cv.imencode('.jpg', frame)
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # If encoding fails, yield an empty frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')

# YOLO-based QR code scanning
def _clip(v, lo, hi):
    return max(lo, min(int(v), hi))

def make_info_panel(lines, photo_img=None, logo_img=None, panel_size=(480, 480)):
    h, w = panel_size
    panel = 255 * np.ones((h, w, 3), dtype=np.uint8)  # white background

    if logo_img is not None:
        if logo_img.shape[2] == 4:  # alpha channel
            lh, lw = logo_img.shape[:2]
            scale = 60 / lh
            new_w, new_h = int(lw*scale), int(lh*scale)
            logo_resized = cv.resize(logo_img, (new_w, new_h))
            b, g, r, a = cv.split(logo_resized)
            logo_rgb = cv.merge((b, g, r))
            mask = a.astype(float)/255.0
            x_offset = (w - new_w)//2
            y_offset = 10
            roi = panel[y_offset:y_offset+new_h, x_offset:x_offset+new_w]
            for c in range(3):
                roi[:,:,c] = (1-mask)*roi[:,:,c] + mask*logo_rgb[:,:,c]
            panel[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = roi
        else:
            lh, lw = logo_img.shape[:2]
            scale = 60/lh
            new_w, new_h = int(lw*scale), int(lh*scale)
            logo_resized = cv.resize(logo_img, (new_w, new_h))
            x_offset = (w - new_w)//2
            panel[10:10+new_h, x_offset:x_offset+new_w] = logo_resized

    # Student photo
    if photo_img is not None:
        ph, pw = photo_img.shape[:2]
        scale = min((h//3)/ph, (w-40)/pw)
        new_w, new_h = int(pw*scale), int(ph*scale)
        photo_resized = cv.resize(photo_img, (new_w, new_h))
        x_offset = (w - new_w)//2
        panel[80:80+new_h, x_offset:x_offset+new_w] = photo_resized
        y_text = 80 + new_h + 20
    else:
        y_text = 100

    for line in lines:
        cv.putText(panel, line, (20, y_text), cv.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2, cv.LINE_AA)
        y_text += 35

    return panel

def zbar_scan_qrcode_generator(camera, latest_scan_result, logo_path="static/images/logo.png"):
    has_id = "StudentID" in df.columns
    id_lookup = {str(r["StudentID"]).strip(): r.to_dict() for _, r in df.iterrows()} if has_id else {}
    csv_dir = os.path.dirname(os.path.abspath("dataset/dataset.csv"))
    model = YOLO("yolov8n.pt")
    detector = cv.QRCodeDetector()

    logo_img = cv.imread(logo_path, cv.IMREAD_UNCHANGED) if logo_path else None
    info_panel = make_info_panel(["Waiting for QR Code..."], logo_img=logo_img)

    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        h, w = frame.shape[:2]
        data = None

        # --- YOLO detect QR ---
        results = model(frame, conf=0.25, iou=0.45, verbose=False)
        boxes = []
        if results and len(results) > 0:
            r0 = results[0]
            if r0.boxes is not None and len(r0.boxes) > 0:
                xyxy = r0.boxes.xyxy.cpu().numpy()
                cls = r0.boxes.cls.cpu().numpy().astype(int)
                confs = r0.boxes.conf.cpu().numpy()
                for (x1, y1, x2, y2), c, cf in zip(xyxy, cls, confs):
                    boxes.append((x1, y1, x2, y2, cf))

        if boxes:
            x1, y1, x2, y2, cf = max(boxes, key=lambda x: x[4])
            x1p, y1p = _clip(x1-8, 0, w-1), _clip(y1-8, 0, h-1)
            x2p, y2p = _clip(x2+8, 0, w-1), _clip(y2+8, 0, h-1)
            roi = frame[y1p:y2p, x1p:x2p]
            if roi.size > 0:
                data, _, _ = detector.detectAndDecode(roi)
                if not data:
                    # Retry with scaled-up ROI
                    for scale in (1.5, 2.0):
                        roi_big = cv.resize(roi, None, fx=scale, fy=scale)
                        data, _, _ = detector.detectAndDecode(roi_big)
                        if data:
                            break
                if data:
                    cv.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (36, 255, 12), 3)

        if not data:
            data, _, _ = detector.detectAndDecode(frame)

        if data:
            info = parse_qr_text(data)
            lines = []
            photo_img = None

            sid = str(info.get("StudentID", "")).strip()

            if sid and has_id:
                row = id_lookup.get(sid)
                if row:
                    lines = [
                        f"Name: {row.get('Name','')}",
                        f"Student ID: {row.get('StudentID','')}",
                        f"Faculty: {row.get('Faculty','')}",
                        f"Course: {row.get('Course','')}",
                        f"CGPA: {row.get('CGPA','')}",
                    ]
                    if "Photo" in row and row["Photo"]:
                        photo_path = os.path.join(csv_dir, str(row["Photo"]).replace("/", os.sep))
                        if os.path.exists(photo_path):
                            photo_img = cv.imread(photo_path)

                    # --- Update recognition result ---
                    if isinstance(latest_scan_result, dict):
                        latest_scan_result.clear()
                        latest_scan_result.update({
                            "type": "qrcode",
                            "data": sid,
                            "info": row
                        })
                else:
                    lines = [f"Unregistered Student ID: {sid}"]
            else:
                # Show raw QR contents if not matched
                lines = [f"{k}: {v}" for k, v in info.items()]

            info_panel = make_info_panel(lines, photo_img, logo_img)

        # --- Combine camera + info panel ---
        cam_resized = cv.resize(frame, (640, 480))
        info_resized = cv.resize(info_panel, (480, 480))
        combined = np.hstack((cam_resized, info_resized))

        # Encode as JPEG
        ret, buffer = cv.imencode('.jpg', combined)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'\r\n')

def parse_qr_text(qr_text: str) -> dict:
    info = {}
    for line in str(qr_text).splitlines():
        m = re.match(r"\s*([^:]+)\s*:\s*(.*)\s*$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            info[key] = val

    # Normalize: allow both "ID" and "StudentID"
    if "ID" in info and "StudentID" not in info:
        info["StudentID"] = info["ID"]

    return info
