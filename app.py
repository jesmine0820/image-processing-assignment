import traceback
import time
import sqlite3
from flask import Flask, render_template, Response, request, jsonify, session
from database import create_recog_db, generate_barcodes
from camera import CameraStream
from tracking import track_person
from face_recognition import real_time_pipeline, real_time
from barcode_detection import (
    scan_barcode_generator, scan_qr_code_generator,
    scan_barcode_py_generator, scan_qr_py_generator,
    get_latest_scan_result, reset_scan_result
)
from gmail import send_graduation_tickets

app = Flask(__name__)
app.secret_key = "image_processing_assignment"

# Initializer
latest_recognition = {
    1: {"id": "---", "name": "---"},
    2: {"id": "---", "name": "---"},
    3: {"id": "---", "name": "---"}
}

queue_list = []
current_person_index = 0

# Init DB
create_recog_db()

# Selected models (default)
selected_models = {
    "face": "insightFace",
    "barcode": "zxing"
}

# --- Camera Pool ---
cameras = {}

def get_camera(index=0):
    cam = cameras.get(index)
    if cam is None:
        cam = CameraStream(index).start()
        cameras[index] = cam
    return cam

def release_all_cameras():
    for idx, cam in list(cameras.items()):
        cam.stop()
        del cameras[idx]

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/recognition/<int:counter>")
def recognition(counter):
    try:
        if counter == 2:  # Barcode/QR code recognition
            scan_result = get_latest_scan_result()
            if scan_result and scan_result["type"]:
                return {
                    "id": scan_result["data"],
                    "name": scan_result["info"]["Name"] if scan_result["info"] else "---"
                }
            return {"id": "---", "name": "---"}
        else:  # Face recognition
            return latest_recognition.get(counter, {"id": "---", "name": "---"})
    except Exception as e:
        print(f"Error in recognition route: {e}")
        traceback.print_exc()
        return {"id": "---", "name": "---"}, 500

@app.route("/video/<int:counter>")
def video(counter):
    try:
        mode = request.args.get("mode", "face")
        camera = get_camera(0)

        if counter == 1:
            if mode == "face":
                if selected_models["face"] == "insightFace":
                    generator = real_time_pipeline(camera, latest_recognition)
                else:
                    generator = real_time(camera, latest_recognition)
            else:
                generator = scan_barcode_generator(camera) if selected_models["barcode"] == "zxing" else scan_barcode_py_generator(camera)

        elif counter == 2:
            generator = scan_barcode_generator(camera) if selected_models["barcode"] == "zxing" else scan_barcode_py_generator(camera)

        elif counter == 3:
            generator = track_person()
        else:
            generator = real_time_pipeline(camera, latest_recognition)

        return Response(generator, mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception as e:
        print(f"Error in video route: {e}")
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
    try:
        generate_barcodes()
        send_graduation_tickets()
        return jsonify({"message": "Graduation emails sent successfully!"})
    except Exception as e:
        print("Error in send_graduation_emails:", e)
        traceback.print_exc()
        return jsonify({"message": f"Failed to send graduation emails: {str(e)}"}), 500

@app.route("/verify-identity", methods=["POST"])
def verify_identity():
    try:
        data = request.json
        face_id = data.get("face_id")
        barcode_id = data.get("barcode_id")
        
        if face_id and barcode_id and face_id == barcode_id:
            # Store the verified ID in session for QR generation
            session["verified_id"] = face_id
            
            # Save to database only if not exists
            conn = sqlite3.connect("database/recognized_people.db")
            cursor = conn.cursor()
            
            # Check if person already exists
            cursor.execute("SELECT * FROM recognized_people WHERE person_id = ?", (face_id,))
            existing = cursor.fetchone()
            
            if not existing:
                # Get person info from dataset
                dataset_df = pd.read_csv("dataset/dataset.csv")
                person_info = dataset_df[dataset_df["StudentID"] == face_id]
                
                if not person_info.empty:
                    name = person_info.iloc[0]["Name"]
                    # Insert into database
                    cursor.execute(
                        "INSERT INTO recognized_people (person_id, name, counter_id) VALUES (?, ?, ?)",
                        (face_id, name, "1")
                    )
                    conn.commit()
                    
                    # Generate QR code (you'll need to implement this)
                    # For now, we'll just return the ID
                    return jsonify({
                        "status": "success", 
                        "message": "Identity verified successfully",
                        "id": face_id,
                        "name": name
                    })
            
            conn.close()
            return jsonify({
                "status": "error", 
                "message": "Person already registered or not found in dataset"
            }), 400
        else:
            return jsonify({
                "status": "error", 
                "message": "Face ID and Barcode ID do not match"
            }), 400
            
    except Exception as e:
        print(f"Error in verify-identity route: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

# Add this route for QR code scanning at counter 2
@app.route("/add-to-queue", methods=["POST"])
def add_to_queue():
    try:
        data = request.json
        qr_id = data.get("qr_id")
        
        # Check if person is already in queue
        if any(person["id"] == qr_id for person in queue_list):
            return jsonify({
                "status": "error", 
                "message": "Person already in queue"
            }), 400
        
        # Get person info from dataset
        dataset_df = pd.read_csv("dataset/dataset.csv")
        person_info = dataset_df[dataset_df["StudentID"] == qr_id]
        
        if not person_info.empty:
            name = person_info.iloc[0]["Name"]
            person_data = {
                "id": qr_id,
                "name": name,
                "is_current": "N"
            }
            queue_list.append(person_data)
            
            return jsonify({
                "status": "success", 
                "message": "Person added to queue",
                "id": qr_id,
                "name": name
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "Person not found in dataset"
            }), 400
            
    except Exception as e:
        print(f"Error in add-to-queue route: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

# Add this route to get queue list
@app.route("/get-queue")
def get_queue():
    return jsonify(queue_list)

# Add this route to update current person
@app.route("/update-current-person", methods=["POST"])
def update_current_person():
    try:
        global current_person_index
        
        # Find the next person who is not current
        for i, person in enumerate(queue_list):
            if person["is_current"] == "N":
                # Set this person as current
                queue_list[i]["is_current"] = "Y"
                current_person_index = i
                return jsonify({
                    "status": "success", 
                    "person": person
                })
        
        return jsonify({
            "status": "error", 
            "message": "No more people in queue"
        }), 400
            
    except Exception as e:
        print(f"Error in update-current-person route: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

# Add this route to mark person as done
@app.route("/mark-person-done", methods=["POST"])
def mark_person_done():
    try:
        global current_person_index
        
        if queue_list and current_person_index < len(queue_list):
            # Remove the current person from queue
            queue_list.pop(current_person_index)
            
            # Reset index
            if queue_list:
                current_person_index = 0
                queue_list[0]["is_current"] = "Y"
            else:
                current_person_index = 0
            
            return jsonify({
                "status": "success", 
                "message": "Person marked as done"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "No current person to mark as done"
            }), 400
            
    except Exception as e:
        print(f"Error in mark-person-done route: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Server error"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
