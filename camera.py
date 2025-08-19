import cv2 as cv
import threading
import time

class CameraStream:
    def __init__(self, src=0, width=None, height=None):
        self.cap = cv.VideoCapture(src, cv.CAP_DSHOW)
        if width is not None:
            self.cap.set(cv.CAP_PROP_FRAME_WIDTH, width)
        if height is not None:
            self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, height)

        self.frame = None
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        if self.running:
            return self
        self.running = True
        t = threading.Thread(target=self._update, daemon=True)
        t.start()
        return self

    def _update(self):
        while self.running:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                else:
                    # brief backoff if grab failed
                    time.sleep(0.01)
            else:
                # try to reopen if needed
                self.cap.open(self.cap.get(cv.CAP_PROP_POS_FRAMES))
                time.sleep(0.1)

    def get_frame(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        time.sleep(0.05)
        if self.cap.isOpened():
            self.cap.release()
