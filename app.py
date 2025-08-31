from flask import Flask, render_template, Response, request, jsonify
from database import create_recog_db
from camera import CameraStream
from tracking import track_person
from face_recognition import real_time_pipeline, real_time
from barcode_detection import (
    scan_barcode_generator, scan_qr_code_generator, 
    scan_barcode_py_generator, scan_qr_py_generator,
    get_latest_scan_result, reset_scan_result, student_dict
)
import traceback

app = Flask(__name__)
app.secret_key = "image_processing_assignment"

# Initializer
latest_recognition = {
    1: {"id": "---", "name": "---"},
    2: {"id": "---", "name": "---"},
    3: {"id": "---", "name": "---"}
}

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
            data = latest_recognition.get(counter, {"id": "---", "name": "---"})
            return data
    except Exception as e:
        print(f"Error in recognition route: {e}")
        traceback.print_exc()
        return {"id": "---", "name": "---"}, 500

# In your Flask app
@app.route("/video/<int:counter>")
def video(counter):
    try:
        mode = request.args.get("mode", "face")
        camera = get_camera(0)

        generator = None

        if counter == 1:
            if mode == "face":
                if selected_models["face"] == "insightFace":
                    generator = real_time_pipeline(camera, latest_recognition)
                else:
                    print("Yes")
                    generator = real_time(camera, latest_recognition)  # New function for MTCNN
            elif mode == "barcode":
                if selected_models["barcode"] == "zxing":
                    generator = scan_barcode_generator(camera)
                else:
                    generator = scan_barcode_py_generator(camera)
        elif counter == 2:
            if selected_models["barcode"] == "zxing":
                generator = scan_barcode_generator(camera)
            else:
                generator = scan_barcode_py_generator(camera)
        elif counter == 3:
            generator = track_person()
        
        if generator is None:
            generator = real_time_pipeline(camera, latest_recognition)

        return Response(generator, mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception as e:
        print(f"Error in video route: {e}")
        traceback.print_exc()
        return "Server Error", 500

@app.route("/get-settings")
def get_settings():
    try:
        return jsonify(selected_models)
    except Exception as e:
        print(f"Error in get-settings route: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/save-settings", methods=["POST"])
def save_settings():
    try:
        data = request.json
        selected_models["face"] = data.get("face", "insightFace")
        selected_models["barcode"] = data.get("barcode", "zxing")
        return jsonify({"status": "success", "selected": selected_models})
    except Exception as e:
        print(f"Error in save-settings route: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/reset-scan")
def reset_scan():
    try:
        reset_scan_result()
        return jsonify({"status": "scan reset"})
    except Exception as e:
        print(f"Error in reset-scan route: {e}")
        return jsonify({"error": "Server error"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)