import os
import sqlite3
import pandas as pd
from flask import (
    Flask, Response,
    render_template, jsonify,
    request, session, send_from_directory
)

# --- Local modules ---
from database import create_recog_db, set_attendance, has_attendance_yes
from camera import CameraStream
from tracking import track_person
from face_recognition import real_time_pipeline, real_time
from barcode_detection import (
    scan_barcode_generator, scan_qr_code_generator,
    scan_barcode_py_generator, zbar_scan_qrcode_generator,
    generate_qr_code
)
from gmail import send_graduation_tickets, send_qrcode
from tts import speak   # ✅ our updated TTS

# --- Flask app initializer ---
app = Flask(__name__)
app.secret_key = "image_processing_assignment"

# --- Global state ---
latest_recognition = {
    1: {"id": "---", "name": "---"},
    2: {"id": "---", "name": "---"},
    3: {"id": "---", "name": "---"}
}
latest_scan_result = {"type": None, "data": None, "info": None}
queue_list = []
selected_models = {"face": "insightFace", "barcode": "zxing"}
cameras = {}

# --- Init database ---
create_recog_db()

# Camera handling
def get_camera(index=0):
    if index not in cameras:
        cameras[index] = CameraStream(index).start()
    return cameras[index]

def release_all_cameras():
    for idx, cam in list(cameras.items()):
        cam.stop()
        del cameras[idx]

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/photos/<filename>")
def serve_photo(filename):
    """Serve photos from /photos directory"""
    try:
        return send_from_directory("photos", filename)
    except FileNotFoundError:
        return send_from_directory("static/images", "logo.png")

@app.route("/recognition/<int:counter>")
def recognition(counter):
    """
    Returns recognition results depending on counter:
    - Counter 1 → face or barcode
    - Counter 2 → ONLY return details if a QR code was scanned
    - Counter 3 → queue display only
    """
    mode = request.args.get("mode", "face")

    if counter == 1:
        if mode == "face":
            return jsonify(latest_recognition.get(1, {"id": "---", "name": "---"}))
        else:  # barcode mode
            if latest_scan_result and latest_scan_result.get("type") == "barcode":
                return jsonify({
                    "id": latest_scan_result["data"],
                    "name": latest_scan_result["info"].get("Name", "---")
                    if latest_scan_result["info"] else "---"
                })
            return jsonify({"id": "---", "name": "---"})

    elif counter == 2:
        # ✅ Only show details if QR scan has been performed
        if latest_scan_result and latest_scan_result.get("type") == "qrcode":
            return jsonify({
                "id": latest_scan_result["data"],
                "name": latest_scan_result["info"].get("Name", "---")
                if latest_scan_result["info"] else "---"
            })
        return jsonify({"id": "---", "name": "---"})

    return jsonify({"id": "---", "name": "---"})

@app.route("/video/<int:counter>")
def video(counter):
    mode = request.args.get("mode", "face")
    camera = get_camera(0)

    if counter == 1:
        if mode == "face":
            generator = (real_time_pipeline(camera, latest_recognition)
                         if selected_models["face"] == "insightFace"
                         else real_time(camera, latest_recognition))
        else:
            generator = (scan_barcode_generator(camera, latest_scan_result)
                         if selected_models["barcode"] == "zxing"
                         else scan_barcode_py_generator(camera, latest_scan_result))

    elif counter == 2:
        # ✅ QR code scan only at counter 2
        generator = (scan_qr_code_generator(camera, latest_scan_result)
                     if selected_models["barcode"] == "zxing"
                     else zbar_scan_qrcode_generator(camera, latest_scan_result))

    elif counter == 3:
        generator = track_person(camera)

    else:
        generator = real_time_pipeline(camera, latest_recognition)

    return Response(generator, mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/get-settings")
def get_settings():
    return jsonify(selected_models)

@app.route("/save-settings", methods=["POST"])
def save_settings():
    data = request.json
    selected_models["face"] = data.get("face", "insightFace")
    selected_models["barcode"] = data.get("barcode", "zxing")
    return jsonify({"status": "success", "selected": selected_models})

@app.route("/reset-scan")
def reset_scan():
    latest_scan_result.clear()
    latest_scan_result.update({"type": None, "data": None, "info": None})
    return jsonify({"status": "reset"})

@app.route("/send-graduation-emails", methods=["POST"])
def send_graduation_emails():
    try:
        send_graduation_tickets()
        return jsonify({"message": "Graduation emails sent successfully!"})
    except Exception as e:
        return jsonify({"message": f"Failed to send emails: {str(e)}"}), 500

@app.route("/verify-identity", methods=["POST"])
def verify_identity():
    try:
        data = request.json
        face_id, barcode_id = data.get("face_id"), data.get("barcode_id")

        if not (face_id and barcode_id):
            return jsonify({"status": "error", "message": "Missing IDs"}), 400
        if face_id != barcode_id:
            return jsonify({"status": "error", "message": "Face ID and Barcode ID do not match"}), 400

        session["verified_id"] = face_id
        conn = sqlite3.connect("database/recognized_people.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM recognized_people WHERE person_id = ?", (face_id,))
        existing = cursor.fetchone()

        if not existing:
            dataset_df = pd.read_csv("dataset/dataset.csv")
            person_info = dataset_df[dataset_df["StudentID"] == face_id]

            if not person_info.empty:
                name = person_info.iloc[0]["Name"]
                cursor.execute(
                    "INSERT INTO recognized_people (person_id, name, attendance) VALUES (?, ?, ?)",
                    (face_id, name, "Y")
                )
                conn.commit()
                conn.close()

                # Generate QR + email
                info = {"StudentID": face_id,
                        "Name": name,
                        "Faculty": person_info.iloc[0].get("Faculty", ""),
                        "CGPA": person_info.iloc[0].get("CGPA", "")}
                generate_qr_code(face_id, info)
                send_qrcode(face_id)

                return jsonify({
                    "status": "success",
                    "id": face_id,
                    "name": name,
                    "message": "Attendance recorded and QR code emailed!"
                })

        conn.close()
        return jsonify({"status": "error", "message": "Already registered or not found"}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500

@app.route("/add-to-queue", methods=["POST"])
def add_to_queue():
    try:
        data = request.json
        qr_id = data.get("qr_id")

        if any(person["id"] == qr_id for person in queue_list):
            return jsonify({"status": "error", "message": "Already in queue"}), 400

        dataset_df = pd.read_csv("dataset/dataset.csv")
        person_info = dataset_df[dataset_df["StudentID"] == qr_id]

        if not person_info.empty and has_attendance_yes(qr_id):
            name = person_info.iloc[0]["Name"]
            has_current = any(p.get("is_current") == "Y" for p in queue_list)
            is_current_flag = "Y" if not has_current else "N"
            queue_list.append({"id": qr_id, "name": name, "is_current": is_current_flag})
            return jsonify({"status": "success", "id": qr_id, "name": name})

        return jsonify({"status": "error", "message": "Invalid QR or attendance not confirmed"}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500

@app.route("/get-queue")
def get_queue():
    return jsonify(queue_list)

@app.route("/update-current-person", methods=["POST"])
def update_current_person():
    try:
        if not queue_list:
            # Instead of error, just return gracefully if empty
            return jsonify({"status": "error", "message": "Queue is empty"}), 200

        current_index = next((i for i, p in enumerate(queue_list) if p["is_current"] == "Y"), -1)

        if current_index == -1:
            queue_list[0]["is_current"] = "Y"
            speak(queue_list[0]["id"])  # 🔊 announce first person
            return jsonify({"status": "success", "person": queue_list[0], "more_people": len(queue_list) > 1})

        elif current_index + 1 < len(queue_list):
            queue_list[current_index]["is_current"] = "N"
            queue_list[current_index + 1]["is_current"] = "Y"
            speak(queue_list[current_index + 1]["id"])  # 🔊 announce next person
            return jsonify({"status": "success", "person": queue_list[current_index + 1], "more_people": current_index + 2 < len(queue_list)})

        else:
            # ✅ If last person, still speak once
            speak(queue_list[current_index]["id"])
            return jsonify({"status": "success", "person": queue_list[current_index], "more_people": False})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500


@app.route("/mark-person-done", methods=["POST"])
def mark_person_done():
    try:
        if queue_list:
            queue_list.pop(0)
            if queue_list:
                queue_list[0]["is_current"] = "Y"
                speak(queue_list[0]["id"])  # 🔊 auto announce promoted person
            return jsonify({"status": "success", "message": "Person marked as done"})
        return jsonify({"status": "error", "message": "Queue empty"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
