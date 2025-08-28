from flask import Flask, render_template, Response, request, redirect, url_for, session
from database import create_recog_db
from camera import CameraStream
from tracking import track_person
from fr_insightFace import real_time_pipeline

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

# --- Camera Pool ---
cameras = {}

def get_camera(index=0):
    """Get or create a shared CameraStream for the given index."""
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
    data = latest_recognition.get(counter, {"id": "---", "name": "---"})
    return data

@app.route("/video/<int:counter>")
def video(counter):

    mode = request.args.get("mode", "face")

    camera = get_camera(0)

    if counter == 1:
        generator = real_time_pipeline(camera, latest_recognition)
    elif counter == 2:
        generator = real_time_pipeline(camera)
    elif counter == 3:
        generator =  track_person()
    else:
        # default fallback
        generator = real_time_pipeline(camera)

    return Response(generator, mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
