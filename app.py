from flask import Flask, render_template, Response, request, redirect, url_for, session
from faceRecognition import insightFace
from barcode_scanner import barcode_scanner
from database import create_recog_db
from camera import CameraStream
from tracking import track_person

app = Flask(__name__)
app.secret_key = "image_processing_assignment"

# Users
users = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"},
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
    return render_template("login.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        user = users.get(username)
        if user and user["password"] == password and user["role"] == role:
            session["username"] = username
            session["role"] = role
            return redirect(url_for("admin_dashboard" if role == "admin" else "user_dashboard"))
        else:
            error = "Invalid username, password, or role!"
    return render_template("login.html", error=error)

@app.route("/admin_dashboard")
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/user_dashboard")
def user_dashboard():
    get_camera(0)
    return render_template("user_dashboard.html")

@app.route("/logout")
def logout():
    session.clear()
    release_all_cameras()
    return redirect(url_for("login"))

@app.route("/video/<int:counter>")
def video(counter):

    mode = request.args.get("mode", "face")

    camera = get_camera(0)

    if counter == 1:
        generator = barcode_scanner(camera) if mode == "barcode" else insightFace(camera)
    elif counter == 2:
        generator = barcode_scanner(camera)
    elif counter == 3:
        generator =  track_person()
    else:
        # default fallback
        generator = barcode_scanner(camera)

    return Response(generator, mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
