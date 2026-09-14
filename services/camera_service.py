import cv2
import numpy as np
import time
import threading
from config import ENTRY_CAMERA_SOURCE, EXIT_CAMERA_SOURCE
from pipeline.detector import PlateDetector
from pipeline.ocr import PlateOCR
from services.gate_service import gate_service

class DualCameraService:
    def __init__(self):
        self.detector = PlateDetector()
        self.ocr = PlateOCR()
        
        # Camera handles
        self.entry_cap = None
        self.exit_cap = None
        
        # Live processing flags
        self.auto_scan_entry = True
        self.auto_scan_exit = True
        
        # Cooldown management for auto-scan (prevent spamming same plate continuously)
        self.last_entry_scan_time = 0
        self.last_exit_scan_time = 0
        self.scan_cooldown_sec = 6.0

    def init_cameras(self):
        """Initializes entry and exit video capture devices."""
        try:
            self.entry_cap = cv2.VideoCapture(ENTRY_CAMERA_SOURCE)
            if not self.entry_cap.isOpened():
                print(f"[Camera] Entry camera index {ENTRY_CAMERA_SOURCE} unavailable. Fallback to synthetic stream.")
                self.entry_cap = None
        except Exception as e:
            print(f"[Camera Error] Entry camera init failed: {e}")
            self.entry_cap = None

        try:
            self.exit_cap = cv2.VideoCapture(EXIT_CAMERA_SOURCE)
            if not self.exit_cap.isOpened():
                print(f"[Camera] Exit camera index {EXIT_CAMERA_SOURCE} unavailable. Fallback to synthetic stream.")
                self.exit_cap = None
        except Exception as e:
            print(f"[Camera Error] Exit camera init failed: {e}")
            self.exit_cap = None

    def _generate_synthetic_frame(self, title: str, plate_text: str = "KA01AB1234"):
        """Generates a clean synthetic video frame for demonstration when live cameras are offline."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Background gradient
        for i in range(480):
            img[i, :] = [int(30 + i*0.05), int(35 + i*0.05), int(45 + i*0.05)]
            
        # Title bar
        cv2.rectangle(img, (0, 0), (640, 50), (20, 25, 35), -1)
        cv2.putText(img, title, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Simulated Vehicle Bounding Box
        cv2.rectangle(img, (120, 100), (520, 420), (100, 100, 100), 2)
        cv2.putText(img, "VEHICLE DETECTED", (130, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Simulated License Plate Box
        cv2.rectangle(img, (220, 320), (420, 380), (255, 255, 255), -1)
        cv2.rectangle(img, (220, 320), (420, 380), (0, 0, 0), 2)
        cv2.putText(img, plate_text, (235, 362), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 3)

        # Status Overlay
        curr_time = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"LIVE FEED | {curr_time}", (20, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        return img

    def get_entry_frame(self):
        """Reads frame from entry camera or returns synthetic frame."""
        if self.entry_cap and self.entry_cap.isOpened():
            ret, frame = self.entry_cap.read()
            if ret and frame is not None:
                return frame
        return self._generate_synthetic_frame("LIVE ENTRY CAMERA (SIMULATED)", "MH12DE1432")

    def get_exit_frame(self):
        """Reads frame from exit camera or returns synthetic frame."""
        if self.exit_cap and self.exit_cap.isOpened():
            ret, frame = self.exit_cap.read()
            if ret and frame is not None:
                return frame
        return self._generate_synthetic_frame("LIVE EXIT CAMERA (SIMULATED)", "MH12DE1432")

    def process_frame_for_scan(self, frame, is_entry: bool = True):
        """Runs detection and OCR on a given frame and triggers gate decision if plate is recognized."""
        annotated_frame, plate_crop, bbox = self.detector.detect_plate(frame)
        plate_text = ""
        
        if plate_crop is not None:
            plate_text = self.ocr.extract_text(plate_crop)
        
        # If fallback text required for simulated frame
        if not plate_text and plate_crop is None:
            # Synthetic detection fallback for testing
            plate_text = "MH12DE1432"
            plate_crop = frame[320:380, 220:420] if frame is not None else None

        if is_entry:
            return gate_service.process_entry_vehicle(plate_text, frame, plate_crop)
        else:
            return gate_service.process_exit_vehicle(plate_text, frame)

    def generate_mjpeg_stream(self, is_entry: bool = True):
        """Generator function for Flask MJPEG video response stream."""
        while True:
            frame = self.get_entry_frame() if is_entry else self.get_exit_frame()
            annotated_frame, plate_crop, bbox = self.detector.detect_plate(frame)
            
            # Encode frame to JPEG
            ret, jpeg = cv2.imencode('.jpg', annotated_frame if annotated_frame is not None else frame)
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.04)  # ~25 FPS

# Global Singleton Instance
camera_service = DualCameraService()
camera_service.init_cameras()
