import cv2
import numpy as np
import time
import threading
from datetime import datetime
from anpr.plate_detector import PlateDetector
from anpr.vehicle_detector import VehicleDetector

from anpr.ocr import PlateOCR, crop_with_padding
from anpr.recognizer import MultiFrameRecognizer
from anpr.processor import ANPRProcessor
from gate.gate_controller import gate_controller

class CameraService:
    def __init__(self, camera_url=0, name="Camera", enable_detection_overlay=True, is_entry=True):
        self.camera_url = camera_url
        self.name = name
        self.is_entry = is_entry
        self.cap = None
        self.is_connected = False
        self.lock = threading.Lock()
        self.last_reconnect_time = 0
        self.reconnect_interval_sec = 3.0
        self._running = False
        
        self.enable_detection_overlay = enable_detection_overlay
        self.plate_detector = PlateDetector() if enable_detection_overlay else None
        self.vehicle_detector = VehicleDetector() if enable_detection_overlay else None
        self.plate_ocr = PlateOCR() if enable_detection_overlay else None
        self.multi_frame_recognizer = MultiFrameRecognizer() if enable_detection_overlay else None
        self.anpr_processor = ANPRProcessor() if enable_detection_overlay else None

    def start(self):
        """Starts the camera video capture connection."""
        with self.lock:
            if self.cap is not None:
                self.cap.release()
            
            try:
                self.cap = cv2.VideoCapture(self.camera_url)
                if self.cap and self.cap.isOpened():
                    self.is_connected = True
                    print(f"[{self.name}] Successfully connected to camera source: {self.camera_url}")
                else:
                    self.is_connected = False
                    print(f"[{self.name} Warning] Could not open camera source: {self.camera_url}")
            except Exception as e:
                self.is_connected = False
                print(f"[{self.name} Error] Camera initialization failed: {e}")
            
            self._running = True

    def stop(self):
        """Stops and releases the camera handle."""
        with self.lock:
            self._running = False
            self.is_connected = False
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            print(f"[{self.name}] Camera stopped and released.")

    def release(self):
        """Alias for stop()."""
        self.stop()

    @property
    def is_running(self):
        return self._running

    def _try_reconnect(self):
        """Attempts to reconnect to the camera source after disconnection."""
        now = time.time()
        if now - self.last_reconnect_time < self.reconnect_interval_sec:
            return
        
        self.last_reconnect_time = now
        print(f"[{self.name}] Attempting to reconnect to {self.camera_url}...")
        
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        
        try:
            self.cap = cv2.VideoCapture(self.camera_url)
            if self.cap and self.cap.isOpened():
                ret, test_frame = self.cap.read()
                if ret and test_frame is not None:
                    self.is_connected = True
                    print(f"[{self.name}] Reconnected successfully!")
                    return
            self.is_connected = False
        except Exception as e:
            self.is_connected = False
            print(f"[{self.name} Reconnect Error] {e}")

    def read_frame(self):
        """
        Thread-safe frame retrieval.
        Returns live BGR video frame if connected, or offline status frame if disconnected.
        """
        with self.lock:
            if not self._running:
                self.start()

            if self.is_connected and self.cap is not None and self.cap.isOpened():
                try:
                    ret, frame = self.cap.read()
                    if ret and frame is not None and frame.size > 0:
                        return frame
                    else:
                        print(f"[{self.name}] Empty frame received. Connection lost.")
                        self.is_connected = False
                except Exception as e:
                    print(f"[{self.name} Read Error] {e}")
                    self.is_connected = False

            # Auto-reconnection attempt
            self._try_reconnect()
            
            # Return offline status frame
            return self._generate_offline_frame()

    def _generate_offline_frame(self):
        """Generates a clean status overlay frame when live camera stream is offline/reconnecting."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Subtle dark gradient background
        for i in range(480):
            img[i, :] = [int(15 + i*0.03), int(23 + i*0.03), int(42 + i*0.03)]
            
        # Top Header Bar
        cv2.rectangle(img, (0, 0), (640, 50), (30, 41, 59), -1)
        cv2.putText(img, f"{self.name.upper()} FEED", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (248, 250, 252), 2)
        
        # Status Badge (OFFLINE / RECONNECTING)
        cv2.rectangle(img, (160, 180), (480, 280), (30, 41, 59), -1)
        cv2.rectangle(img, (160, 180), (480, 280), (239, 68, 68), 2)
        cv2.putText(img, "CAMERA DISCONNECTED", (185, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (239, 68, 68), 2)
        cv2.putText(img, f"Source: {self.camera_url}", (210, 255), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (148, 163, 184), 1)

        # Bottom Timestamp & Info Bar
        curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"STATUS: RECONNECTING... | {curr_time}", (20, 455), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1)

        return img

    def generate_mjpeg_stream(self, fps=25):
        """
        Generator function producing MJPEG video frames for Flask stream HTTP responses.
        Annotates live camera frame with vehicle (green), plate (yellow), OCR, authorization decision, and ENTRY event logging.
        """
        delay = 1.0 / fps
        while True:
            raw_frame = self.read_frame()
            display_frame = raw_frame.copy() if raw_frame is not None else self._generate_offline_frame()

            if self.enable_detection_overlay and self.is_connected and raw_frame is not None:
                plates = self.plate_detector.detect(raw_frame)
                vehicles = self.vehicle_detector.detect(raw_frame) if self.vehicle_detector else None
                
                # Perform OCR & Multi-Frame Temporal Tracking on detected plates
                for p in plates:
                    bbox = (p["x1"], p["y1"], p["x2"], p["y2"])
                    padded_crop = crop_with_padding(raw_frame, bbox, pad_pct=0.05)
                    ocr_res = self.plate_ocr.read_plate(padded_crop or p.get("crop"))
                    p["ocr_info"] = ocr_res
                    
                    # Temporal tracking & confidence-weighted voting
                    temp_res = self.multi_frame_recognizer.process_observation(bbox, ocr_res)
                    p["temporal_info"] = temp_res
                    
                    # Authorization & Software Gate Decision strictly for CONFIRMED plates
                    if temp_res.get("status") == "CONFIRMED":
                        if self.anpr_processor:
                            if self.is_entry:
                                proc_res = self.anpr_processor.process_entry_event(
                                    frame=raw_frame,
                                    plate_crop=padded_crop or p.get("crop"),
                                    temporal_result=temp_res,
                                    camera_id="ENTRY_CAM_1"
                                )
                            else:
                                proc_res = self.anpr_processor.process_exit_event(
                                    frame=raw_frame,
                                    plate_crop=padded_crop or p.get("crop"),
                                    temporal_result=temp_res,
                                    camera_id="EXIT_CAM_1"
                                )
                            p["gate_info"] = proc_res
                        else:
                            gate_res = gate_controller.process_confirmed_plate(temp_res, is_entry=self.is_entry)
                            p["gate_info"] = gate_res

                display_frame = self.plate_detector.draw_detections(display_frame, plates, vehicles)

            ret, jpeg = cv2.imencode('.jpg', display_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(delay)
