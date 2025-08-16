from flask import Flask, render_template, Response, request, redirect, url_for, session
from faceRecognition import real_time_pipeline
from barcode_scanner import barcode_scanner
from database import init_db

app = Flask(__name__)
app.secret_key = "image_processing_assignment"

# Dummy user database
users = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"}
}

# Initialize database
init_db()
      
@app.route('/')
def index():
    return render_template('login.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        if username in users and users[username]["password"] == password and users[username]["role"] == role:
            session["username"] = username
            session["role"] = role

            if role == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))
        else:
            error = "Invalid username, password, or role!"

    return render_template("login.html", error=error)

@app.route("/admin_dashboard")
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route("/user_dashboard")
def user_dashboard():
    return render_template('user_dashboard.html')

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/video/<int:counter>')
def video(counter):
    mode = request.args.get("mode", "face")  # default = face

    if counter == 1:
        if mode == "barcode":
            return Response(barcode_scanner(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')
        else:
            return Response(real_time_pipeline(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

    elif counter == 2:
        return Response(barcode_scanner(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    elif counter == 3:
        return Response(real_time_pipeline(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
