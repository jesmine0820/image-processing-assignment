import cv2 as cv

def barcode_scanner(camera):
    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                continue
            frame = cv.flip(frame, 1)

            ok, buf = cv.imencode(".jpg", frame)
            if not ok:
                continue

            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
    except GeneratorExit:
        return
