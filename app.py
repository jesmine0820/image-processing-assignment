import cv2 as cv
from flask import Flask, render_template, Response
from faceRecognition import real_time_pipeline
from database import init_db

app = Flask(__name__)

# Initialize database
init_db()
      
@app.route('/')
def index():
    return render_template('user_dashboard.html')

@app.route('/video/<int:counter>')
def video(counter):
    return Response(real_time_pipeline(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
