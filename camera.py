import cv2 as cv
import threading
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        """Initialize or reinitialize the camera"""
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
        
        self.cap = cv.VideoCapture(self.src, cv.CAP_DSHOW)
        if self.width is not None:
            self.cap.set(cv.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height is not None:
            self.cap.set(cv.CAP_PROP_FRAME_HEIGHT, self.height)
        
        # Test if camera is working
        if self.cap.isOpened():
            ret, test_frame = self.cap.read()
            if not ret:
                logger.warning("Camera initialized but cannot read frames")
        else:
            logger.error("Failed to initialize camera")

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
                    time.sleep(0.5)  # Give camera time to initialize
                    continue
                
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                    self.retry_count = 0  # Reset retry counter on success
                else:
                    logger.warning("Failed to read frame from camera")
                    self.retry_count += 1
                    if self.retry_count >= self.max_retries:
                        logger.error("Max retries reached, reinitializing camera")
                        self.initialize_camera()
                        self.retry_count = 0
                    time.sleep(0.1)
                    
            except cv.error as e:
                logger.error(f"OpenCV error in camera thread: {e}")
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    logger.error("Max retries reached, reinitializing camera")
                    self.initialize_camera()
                    self.retry_count = 0
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Unexpected error in camera thread: {e}")
                time.sleep(0.1)

    def get_frame(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        time.sleep(0.1)  # Give thread time to exit
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None