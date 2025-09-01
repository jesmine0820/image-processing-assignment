import cv2 as cv
import threading
import time
import numpy as np

class CameraStream:
    def __init__(self, src=0, width=None, height=None):
        self.src = src
        self.width = width
        self.height = height
        self.cap = None
        self.use_dummy = False
        self.dummy_frame = None
        self.initialize_camera()
        
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.retry_count = 0
        self.max_retries = 5

    def create_dummy_frame(self):
        """Create a dummy frame for testing when no camera is available"""
        if self.dummy_frame is None:
            # Create a simple test pattern
            height, width = 480, 640
            self.dummy_frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Add some text and shapes
            cv.putText(self.dummy_frame, "No Camera Available", (50, height//2), 
                      cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv.putText(self.dummy_frame, "Testing Mode", (50, height//2 + 50), 
                      cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # Draw a rectangle
            cv.rectangle(self.dummy_frame, (100, 100), (width-100, height-100), (0, 255, 0), 3)
        
        return self.dummy_frame.copy()

    def initialize_camera(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass

        # Try different camera indices and backends
        camera_indices = [0, 1, -1]  # Try index 0, 1, and auto-detect
        backends = [cv.CAP_DSHOW, cv.CAP_MSMF, cv.CAP_ANY]
        
        for idx in camera_indices:
            for backend in backends:
                try:
                    cap = cv.VideoCapture(idx, backend)
                    if cap.isOpened():
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None:
                            self.cap = cap
                            if self.width is not None:
                                self.cap.set(cv.CAP_PROP_FRAME_WIDTH, self.width)
                            if self.height is not None:
                                self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, self.height)
                            print(f"[INFO] Camera initialized successfully with index {idx} and backend {backend}")
                            return
                        else:
                            cap.release()
                except Exception as e:
                    print(f"[WARN] Failed to initialize camera with index {idx} and backend {backend}: {e}")
                    continue

        # If no camera found, create a dummy camera with test image
        print("[WARN] No camera found, using dummy camera with test image")
        self.cap = None
        self.use_dummy = True

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