import traceback
import sqlite3
import pandas as pd
import logging
from flask import Flask, render_template, Response, request, jsonify, session

# --- Local Modules ---
from database import create_recog_db, generate_barcodes
from camera import CameraStream
from tracking import track_person
from face_recognition import real_time_pipeline, real_time
from barcode_detection import (
    scan_barcode_generator, scan_qr_code_generator,
    scan_barcode_py_generator, zbar_scan_qrcode_generator,
    get_latest_scan_result, reset_scan_result
)
from gmail import send_graduation_tickets

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = "image_processing_assignment"
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

# --- Global Variables ---
latest_recognition = {
    1: {"id": "---", "name": "---"},
    2: {"id": "---", "name": "---"},
    3: {"id": "---", "name": "---"}
}
queue_list = []
current_person_index = 0

# Selected models (default)
selected_models = {"face": "insightFace", "barcode": "zxing"}

# Camera pool
cameras = {}

# --- Database Init ---
create_recog_db()

# --- Camera Handling ---
def get_camera(index=0):
    """Get or create a CameraStream instance."""
    if index not in cameras:
        cameras[index] = CameraStream(index).start()
    return cameras[index]

def release_all_cameras():
    """Release all active camera streams."""
    for idx, cam in list(cameras.items()):
        cam.stop()
        del cameras[idx]

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/recognition/<int:counter>")
def recognition(counter):
    """Return recognition results for a given counter."""
    try:
        mode = request.args.get("mode", "face")

        if counter == 1:
            if mode == "face":
                return latest_recognition.get(1, {"id": "---", "name": "---"})
            elif mode == "barcode":
                scan_result = get_latest_scan_result()
                if scan_result and scan_result.get("type"):
                    return {
                        "id": scan_result["data"],
                        "name": scan_result["info"].get("Name", "---") if scan_result["info"] else "---"
                    }
                return {"id": "---", "name": "---"}

        elif counter == 2:  # QR counter
            scan_result = get_latest_scan_result()
            if scan_result and scan_result.get("type"):
                return {
                    "id": scan_result["data"],
                    "name": scan_result["info"].get("Name", "---") if scan_result["info"] else "---"
                }
            return {"id": "---", "name": "---"}

        # Counter 3 → tracking only, no recognition
        return {"id": "---", "name": "---"}

    except Exception as e:
        log.error(f"[ERROR] Recognition route: {e}")
        traceback.print_exc()
        return {"id": "---", "name": "---"}, 500

@app.route("/video/<int:counter>")
def video(counter):
    """Video streaming for each counter."""
    try:
        mode = request.args.get("mode", "face")
        camera = get_camera(0)

        if counter == 1:
            if mode == "face":
                generator = (
                    real_time_pipeline(camera, latest_recognition)
                    if selected_models["face"] == "insightFace"
                    else real_time(camera, latest_recognition)
                )
            else:  # barcode
                generator = (
                    scan_barcode_generator(camera)
                    if selected_models["barcode"] == "zxing"
                    else scan_barcode_py_generator(camera)
                )

        elif counter == 2:
            generator = (
                scan_qr_code_generator(camera)
                if selected_models["barcode"] == "zxing"
                else zbar_scan_qrcode_generator(camera)
            )

        elif counter == 3:
            log.info("[DEBUG] Counter 3 route hit -> starting track_person()")
            generator = track_person(camera)

        else:
            generator = real_time_pipeline(camera, latest_recognition)

        return Response(generator, mimetype="multipart/x-mixed-replace; boundary=frame")

    except Exception as e:
        log.error(f"[ERROR] Video route: {e}")
        traceback.print_exc()
        return "Server Error", 500

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
    reset_scan_result()
    return jsonify({"status": "reset"})

@app.route("/send-graduation-emails", methods=["POST"])
def send_graduation_emails():
    """Generate barcodes and send graduation emails."""
    try:
        generate_barcodes()
        send_graduation_tickets()
        return jsonify({"message": "Graduation emails sent successfully!"})
    except Exception as e:
        log.error("[ERROR] send_graduation_emails:", e)
        traceback.print_exc()
        return jsonify({"message": f"Failed to send emails: {str(e)}"}), 500

@app.route("/verify-identity", methods=["POST"])
def verify_identity():
    """Verify identity by matching face ID and barcode ID."""
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
                    "INSERT INTO recognized_people (person_id, name, counter_id) VALUES (?, ?, ?)",
                    (face_id, name, "1")
                )
                conn.commit()
                conn.close()
                return jsonify({
                    "status": "success",
                    "message": "Identity verified successfully",
                    "id": face_id,
                    "name": name
                })

        conn.close()
        return jsonify({"status": "error", "message": "Already registered or not found"}), 400

    except Exception as e:
        log.error(f"[ERROR] verify_identity: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route("/add-to-queue", methods=["POST"])
def add_to_queue():
    """Add a person to the waiting queue."""
    try:
        data = request.json
        qr_id = data.get("qr_id")

        if any(person["id"] == qr_id for person in queue_list):
            return jsonify({"status": "error", "message": "Already in queue"}), 400

        dataset_df = pd.read_csv("dataset/dataset.csv")
        person_info = dataset_df[dataset_df["StudentID"] == qr_id]

        if not person_info.empty:
            name = person_info.iloc[0]["Name"]
            queue_list.append({"id": qr_id, "name": name, "is_current": "N"})
            return jsonify({"status": "success", "message": "Added to queue", "id": qr_id, "name": name})

        return jsonify({"status": "error", "message": "Person not found"}), 400

    except Exception as e:
        log.error(f"[ERROR] add_to_queue: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route("/get-queue")
def get_queue():
    return jsonify(queue_list)

@app.route("/update-current-person", methods=["POST"])
def update_current_person():
    """Mark the next person in queue as 'current'."""
    try:
        global current_person_index
        for i, person in enumerate(queue_list):
            if person["is_current"] == "N":
                queue_list[i]["is_current"] = "Y"
                current_person_index = i
                return jsonify({"status": "success", "person": person})

        return jsonify({"status": "error", "message": "No more people in queue"}), 400

    except Exception as e:
        log.error(f"[ERROR] update_current_person: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route("/mark-person-done", methods=["POST"])
def mark_person_done():
    """Remove the current person from the queue."""
    try:
        global current_person_index
        if queue_list and current_person_index < len(queue_list):
            queue_list.pop(current_person_index)
            if queue_list:
                current_person_index = 0
                queue_list[0]["is_current"] = "Y"
            else:
                current_person_index = 0
            return jsonify({"status": "success", "message": "Person marked as done"})
        return jsonify({"status": "error", "message": "No current person"}), 400

    except Exception as e:
        log.error(f"[ERROR] mark_person_done: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

# --- Main Entrypoint ---
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
