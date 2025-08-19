'''
Done liao, dont touch
'''

import cv2 as cv
import threading

class CameraStream:
    def __init__(self, index=0):
        self.cap = cv.VideoCapture(index)
        self.lock = threading.Lock()
        self.frame = None
        self.running = True
        threading.Thread(target=self.update, daemon=True)

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
        
    def release(self):
        self.running = False
        self.cap.release()