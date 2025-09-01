import cv2 as cv
import threading
import time

class CameraStream:
    def __init__(self, src=0, width=None, height=None):
        self.src = src
        self.width = width
        self.height = height
        self.cap = None
        self.initialize_camera()
        
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.retry_count = 0
        self.max_retries = 5

    def initialize_camera(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass

        backends = [cv.CAP_DSHOW, cv.CAP_MSMF, cv.CAP_ANY]
        for backend in backends:
            cap = cv.VideoCapture(self.src, backend)
            if cap.isOpened():
                ret, test_frame = cap.read()
                if ret:
                    self.cap = cap
                    if self.width is not None:
                        self.cap.set(cv.CAP_PROP_FRAME_WIDTH, self.width)
                    if self.height is not None:
                        self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, self.height)
                    return
                else:
                    cap.release()

        self.cap = None

    def start(self):
        if self.running:
            return self
        self.running = True
        t = threading.Thread(target=self._update, daemon=True, name="CameraUpdateThread")
        t.start()
        return self
    
    def _update(self):
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    self.initialize_camera()
                    time.sleep(0.5)
                    continue
                
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                    self.retry_count = 0
                else:
                    self.retry_count += 1
                    if self.retry_count >= self.max_retries:
                        self.initialize_camera()
                        self.retry_count = 0
                    time.sleep(0.1)
                    
            except cv.error as e:
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    self.initialize_camera()
                    self.retry_count = 0
                time.sleep(0.1)
                
            except Exception as e:
                time.sleep(0.1)

    def get_frame(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        time.sleep(0.1)
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None