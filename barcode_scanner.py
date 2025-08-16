import cv2 as cv
from database import init_db

# Initialize database
conn, cursor = init_db()

# InsightFace 
def barcode_scanner():
    # Open webcam
    video = cv.VideoCapture(0)

    while True:
        ret, frame = video.read()
        if not ret:
            break

        frame = cv.flip(frame, 1)

        # Convert frame for Flask
        ret, buffer = cv.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    video.release()
