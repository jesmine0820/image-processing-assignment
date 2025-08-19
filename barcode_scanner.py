import cv2 as cv

def barcode_scanner(camera):
    while True:
        frame = camera.get_frame()
        if frame is None:
            continue 

        frame = cv.flip(frame, 1)

        ret, buffer = cv.imencode('.jpg', frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
