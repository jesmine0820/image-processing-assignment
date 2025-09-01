import sqlite3
import pandas as pd
from flask import (
    Flask, Response,
    render_template, jsonify,
    request, session
)

# --- Local Module
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

# --- Flask app intializer ---
app = Flask(__name__)
app.secret_key = "image_processing_assignment"

# --- Global Variable ---
latest_recognition = {
    1: {"id": "---", "name": "---"},
    2: {"id": "---", "name": "---"},
    3: {"id": "---", "name": "---"}
}
latest_scan_result = {
    "type": None,
    "data": None,
    "info": None
}
queue_list = []
current_person_index = 0
selected_models = {"face": "insightFace", "barcode": "zxing"}
cameras = {}

# --- Database init --- 
create_recog_db()

# --- Camera Handling --- 
def get_camera(index=0):
    if index not in cameras:
        cameras[index] = CameraStream(index).start()
    return cameras[index]

def release_all_cameras():
    for idx, cam in list(cameras.items()):
        cam.stop()
        del cameras[idx]

# --- Route ---
# Start app
@app.route("/")
def index():
    return render_template("index.html")

# Update recognized people
@app.route("/recognition/<int:counter>")
def recognition(counter):
    mode = request.args.get("mode", "face")

    if counter == 1:
        if mode == "face":
            return latest_recognition.get(1, {"id": "---", "name": "---"})
        else:
            if latest_scan_result and latest_scan_result.get("type"):
                return {
                    "id": latest_scan_result["data"],
                    "name": latest_scan_result["info"].get("Name", "---") if latest_scan_result["info"] else "---"
                }
            
    else:
        if latest_scan_result and latest_scan_result.get("type"):
            return {
                "id": latest_scan_result["data"],
                "name": latest_scan_result["info"].get("Name", "---") if latest_scan_result["info"] else "---"
            }
            
# Video Counter
@app.route("/video/<int:counter>")
def video(counter):
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
                scan_barcode_generator(camera, latest_scan_result)
                if selected_models["barcode"] == "zxing"
                else scan_barcode_py_generator(camera, latest_scan_result)
            )

    elif counter == 2:
        generator = (
            scan_qr_code_generator(camera, latest_scan_result)
            if selected_models["barcode"] == "zxing"
            else zbar_scan_qrcode_generator(camera, latest_scan_result)
        )

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
    reset_scan_result()
    return jsonify({"status": "reset"})

@app.route("/send-graduation-emails", methods=["POST"])
def send_graduation_emails():
    try:
        generate_barcodes()
        send_graduation_tickets()
        return jsonify({"message": "Graduation emails sent successfully!"})
    except Exception as e:
        print("[ERROR] send_graduation_emails:", e)
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
        print(f"[ERROR] verify_identity: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route("/add-to-queue", methods=["POST"])
def add_to_queue():
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
        print(f"[ERROR] add_to_queue: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route("/get-queue")
def get_queue():
    return jsonify(queue_list)

@app.route("/update-current-person", methods=["POST"])
def update_current_person():
    try:
        global current_person_index
        for i, person in enumerate(queue_list):
            if person["is_current"] == "N":
                queue_list[i]["is_current"] = "Y"
                current_person_index = i
                return jsonify({"status": "success", "person": person})

        return jsonify({"status": "error", "message": "No more people in queue"}), 400

    except Exception as e:
        print(f"[ERROR] update_current_person: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500

@app.route("/mark-person-done", methods=["POST"])
def mark_person_done():
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
        print(f"[ERROR] mark_person_done: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


# --- App entry ---
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
