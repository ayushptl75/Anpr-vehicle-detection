import cv2
import numpy as np
import time
import threading
import queue
import os
from datetime import datetime

from config import (
    INFERENCE_INTERVAL, EVENT_COOLDOWN_SECONDS,
    PLATE_CONFIDENCE_THRESHOLD
)
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
        self.enable_detection_overlay = enable_detection_overlay
        
        self.cap = None
        self.is_connected = False
        self.is_simulated = False
        self.lock = threading.Lock()
        self.last_reconnect_time = 0
        self.reconnect_interval_sec = 5.0
        self._running = False
        
        # Frame buffers
        self.latest_raw_frame = None
        self.latest_annotated_frame = None
        
        # AI Detection & OCR Components
        self.plate_detector = PlateDetector() if enable_detection_overlay else None
        self.vehicle_detector = VehicleDetector() if enable_detection_overlay else None
        self.plate_ocr = PlateOCR() if enable_detection_overlay else None
        self.multi_frame_recognizer = MultiFrameRecognizer() if enable_detection_overlay else None
        self.anpr_processor = ANPRProcessor(cooldown_sec=EVENT_COOLDOWN_SECONDS) if enable_detection_overlay else None
        
        # Async OCR queue
        self.ocr_queue = queue.Queue(maxsize=2)
        
        # Live UI Status Dictionary
        self.status_lock = threading.Lock()
        self.live_status = {
            "camera_status": "DISCONNECTED",
            "vehicle_detected": "No vehicle",
            "plate_number": "Searching...",
            "ocr_confidence": 0.0,
            "auth_status": "WAITING",
            "access_decision": "PENDING",
            "gate_status": "CLOSED"
        }
        
        # Thread handles
        self.capture_thread = None
        self.ai_thread = None
        self.ocr_thread = None

    def start(self):
        """Starts background capture, AI, and OCR worker threads safely."""
        with self.lock:
            if self._running:
                return

            self._running = True
            
            self.capture_thread = threading.Thread(target=self._capture_loop, name=f"{self.name}-Capture", daemon=True)
            self.capture_thread.start()
            
            if self.enable_detection_overlay:
                self.ai_thread = threading.Thread(target=self._ai_processing_loop, name=f"{self.name}-AI", daemon=True)
                self.ai_thread.start()
                
                self.ocr_thread = threading.Thread(target=self._ocr_worker_loop, name=f"{self.name}-OCR", daemon=True)
                self.ocr_thread.start()
                
            print(f"[{self.name}] CameraService started.")

    def stop(self):
        """Stops all background threads and releases video capture handle."""
        with self.lock:
            self._running = False
            self.is_connected = False
            self.is_simulated = False
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            print(f"[{self.name}] CameraService stopped and released.")

    def release(self):
        """Alias for stop()."""
        self.stop()

    @property
    def is_running(self):
        return self._running

    def _init_capture(self):
        """Attempts to open physical VideoCapture (webcam/RTSP stream). Tries DirectShow on Windows for webcam sources."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        sources_to_try = [self.camera_url]
        if isinstance(self.camera_url, int) and self.camera_url != 0:
            sources_to_try.append(0)

        for src in sources_to_try:
            # 1. Try with cv2.CAP_DSHOW (Windows DirectShow - fast & reliable for USB webcams)
            caps_to_attempt = []
            if isinstance(src, int) and hasattr(cv2, 'CAP_DSHOW'):
                caps_to_attempt.append(cv2.VideoCapture(src, cv2.CAP_DSHOW))
            caps_to_attempt.append(cv2.VideoCapture(src))

            for cap in caps_to_attempt:
                try:
                    if cap and cap.isOpened():
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            self.cap = cap
                            self.is_connected = True
                            self.is_simulated = False
                            self.latest_raw_frame = test_frame
                            self.latest_annotated_frame = test_frame.copy()
                            with self.status_lock:
                                self.live_status["camera_status"] = "CONNECTED"
                            print(f"[{self.name}] Successfully opened physical camera source: {src}")
                            return True
                        else:
                            cap.release()
                except Exception as e:
                    print(f"[{self.name} Hardware Init Error on {src}] {e}")

        # If physical camera is unavailable, check if simulation stream is explicitly enabled via environment variable
        enable_sim = os.environ.get("ENABLE_SIMULATION", "false").lower() == "true"
        if enable_sim:
            print(f"[{self.name}] Physical camera unavailable. Activating Live ANPR Demo Simulation stream.")
            self.is_connected = True
            self.is_simulated = True
            sim_frame = self._generate_simulated_frame()
            self.latest_raw_frame = sim_frame
            self.latest_annotated_frame = sim_frame.copy()
            with self.status_lock:
                self.live_status["camera_status"] = "CONNECTED (SIMULATED)"
            return True

        print(f"[{self.name}] Physical camera unavailable.")
        self.is_connected = False
        self.is_simulated = False
        disc_frame = self._generate_disconnected_frame()
        self.latest_raw_frame = disc_frame
        self.latest_annotated_frame = disc_frame.copy()
        with self.status_lock:
            self.live_status["camera_status"] = "DISCONNECTED"
        return False

    def _generate_simulated_frame(self):
        """Generates realistic live demo video frame with moving vehicle & plate for continuous testing."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)

        # Driveway & Road Lane
        img[0:150, :] = [40, 30, 25] # Sky / background
        cv2.rectangle(img, (120, 150), (520, 480), (60, 60, 65), -1) # Road asphalt
        cv2.line(img, (320, 150), (320, 480), (240, 240, 240), 2) # Lane divider

        # Gate Posts
        cv2.rectangle(img, (80, 130), (120, 320), (30, 30, 140), -1)
        cv2.rectangle(img, (520, 130), (560, 320), (30, 30, 140), -1)

        # Draw Gate Barrier Arm based on live gate status
        is_open = (gate_controller.entry_gate_status if self.is_entry else gate_controller.exit_gate_status) == "OPEN"
        if is_open:
            cv2.line(img, (120, 150), (120, 40), (0, 0, 255), 8) # Raised
        else:
            cv2.line(img, (120, 230), (520, 230), (0, 0, 255), 8) # Down

        # Oscillating vehicle motion simulating approach
        t = time.time() * 0.8
        offset = int(np.sin(t) * 35)

        # Vehicle Body (Car/SUV)
        car_top = 220 + offset
        car_bottom = 400 + offset
        cv2.rectangle(img, (200, car_top), (440, car_bottom), (110, 90, 70), -1)
        cv2.rectangle(img, (230, car_top + 15), (410, car_top + 85), (170, 150, 130), -1)

        # Headlights
        cv2.circle(img, (225, car_top + 130), 12, (220, 255, 255), -1)
        cv2.circle(img, (415, car_top + 130), 12, (220, 255, 255), -1)

        # Clear High-Contrast License Plate
        plate_str = "MH12DE1432" if self.is_entry else "KA01AB1234"
        px1, py1, px2, py2 = 260, car_top + 115, 380, car_top + 155

        cv2.rectangle(img, (px1, py1), (px2, py2), (255, 255, 255), -1)
        cv2.rectangle(img, (px1, py1), (px2, py2), (0, 0, 0), 2)
        cv2.rectangle(img, (px1, py1), (px1 + 14, py2), (220, 120, 0), -1) # IND band
        cv2.putText(img, plate_str, (px1 + 18, py1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)

        # Header Title
        cam_title = f"{self.name.upper()} - LIVE STREAM"
        cv2.rectangle(img, (0, 0), (640, 36), (15, 23, 42), -1)
        cv2.putText(img, cam_title, (15, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (248, 250, 252), 2)

        return img

    def _capture_loop(self):
        """Continuously captures live camera frames into memory buffer."""
        self._init_capture()

        while self._running:
            if self.is_connected:
                if not self.is_simulated and self.cap is not None and self.cap.isOpened():
                    try:
                        ret, frame = self.cap.read()
                        if ret and frame is not None and frame.size > 0:
                            self.latest_raw_frame = frame
                            if not self.enable_detection_overlay or self.latest_annotated_frame is None:
                                self.latest_annotated_frame = frame
                            time.sleep(0.01)
                            continue
                        else:
                            print(f"[{self.name}] Frame read failed.")
                            self.is_connected = False
                            disc_frame = self._generate_disconnected_frame()
                            self.latest_raw_frame = disc_frame
                            self.latest_annotated_frame = disc_frame
                            with self.status_lock:
                                self.live_status["camera_status"] = "DISCONNECTED"
                    except Exception as e:
                        print(f"[{self.name} Read Error] {e}")
                        self.is_connected = False
                        disc_frame = self._generate_disconnected_frame()
                        self.latest_raw_frame = disc_frame
                        self.latest_annotated_frame = disc_frame
                        with self.status_lock:
                            self.live_status["camera_status"] = "DISCONNECTED"

                # If simulated, generate dynamic frame at ~30 FPS
                if self.is_simulated:
                    sim_frame = self._generate_simulated_frame()
                    self.latest_raw_frame = sim_frame
                    if not self.enable_detection_overlay or self.latest_annotated_frame is None:
                        self.latest_annotated_frame = sim_frame
                    time.sleep(0.03)
                    continue

            # Periodically retry reconnecting if disconnected
            now = time.time()
            if now - self.last_reconnect_time > self.reconnect_interval_sec:
                self.last_reconnect_time = now
                self._init_capture()

            time.sleep(0.1)

    def _generate_disconnected_frame(self):
        """Generates a clean overlay image when camera is disconnected to prevent black screen."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:, :] = (30, 24, 18)

        cv2.rectangle(img, (20, 20), (620, 460), (45, 45, 180), 2)

        text = f"{self.name} Disconnected"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
        cv2.putText(img, text, (320 - tw // 2, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (70, 70, 240), 2)

        subtext = "Please check physical camera connection or stream URL"
        (stw, sth), _ = cv2.getTextSize(subtext, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.putText(img, subtext, (320 - stw // 2, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)

        return img

    def _ai_processing_loop(self):
        """Runs vehicle & license plate detection on latest_raw_frame."""
        while self._running:
            time.sleep(INFERENCE_INTERVAL)

            if not self.is_connected or self.latest_raw_frame is None:
                continue

            raw_frame = self.latest_raw_frame.copy()
            if raw_frame is None or raw_frame.size == 0:
                continue

            # 1. Detect vehicles (stricly car, motorcycle, bus, truck; ignores persons)
            vehicles = self.vehicle_detector.detect(raw_frame) if self.vehicle_detector else []

            if not vehicles:
                with self.status_lock:
                    self.live_status["vehicle_detected"] = "NOT DETECTED"
                    if not self.multi_frame_recognizer or not self.multi_frame_recognizer.tracks:
                        self.live_status["plate_number"] = "Searching..."
                        self.live_status["ocr_confidence"] = 0.0
                        self.live_status["auth_status"] = "WAITING"
                        self.live_status["access_decision"] = "PENDING"
                self.latest_annotated_frame = raw_frame
                continue

            v_class = vehicles[0].get("class", "vehicle")
            with self.status_lock:
                self.live_status["vehicle_detected"] = f"DETECTED ({v_class.upper()})"

            # 2. Detect License Plates
            plates = self.plate_detector.detect(raw_frame) if self.plate_detector else []

            for p in plates:
                if p.get("confidence", 0.0) >= PLATE_CONFIDENCE_THRESHOLD:
                    bbox = (p["x1"], p["y1"], p["x2"], p["y2"])
                    padded_crop = crop_with_padding(raw_frame, bbox, pad_pct=0.05)
                    crop_to_send = padded_crop if padded_crop is not None else p.get("crop")

                    # Flush old queue elements so OCR process always consumes the newest frame
                    if self.ocr_queue.full():
                        try:
                            self.ocr_queue.get_nowait()
                        except queue.Empty:
                            pass
                    try:
                        self.ocr_queue.put_nowait((bbox, crop_to_send, raw_frame.copy()))
                    except queue.Full:
                        pass

                if self.multi_frame_recognizer:
                    track_eval = self.multi_frame_recognizer.evaluate_track(
                        list(self.multi_frame_recognizer.tracks.values())[-1]
                    ) if self.multi_frame_recognizer.tracks else {}
                    p["temporal_info"] = track_eval
                    p["gate_info"] = gate_controller.last_entry_decision if self.is_entry else gate_controller.last_exit_decision

            # 3. Render Annotations
            if self.plate_detector:
                self.latest_annotated_frame = self.plate_detector.draw_detections(raw_frame, plates, vehicles)

    def _ocr_worker_loop(self):
        """Asynchronously runs EasyOCR on plate crops & triggers gate decisions."""
        while self._running:
            try:
                bbox, crop, frame = self.ocr_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if crop is None or crop.size == 0 or not self.plate_ocr:
                continue

            ocr_res = self.plate_ocr.read_plate(crop)

            if self.multi_frame_recognizer:
                temp_res = self.multi_frame_recognizer.process_observation(bbox, ocr_res)
                rec_status = temp_res.get("status", "SEARCHING")
                plate_num = temp_res.get("plate_number", "")
                ocr_conf = temp_res.get("ocr_confidence", 0.0)

                with self.status_lock:
                    if plate_num:
                        self.live_status["plate_number"] = plate_num
                        self.live_status["ocr_confidence"] = ocr_conf
                    else:
                        self.live_status["plate_number"] = "Searching..."
                        self.live_status["ocr_confidence"] = 0.0

                if rec_status == "CONFIRMED":
                    if self.anpr_processor:
                        cam_id = "ENTRY_CAM_1" if self.is_entry else "EXIT_CAM_1"
                        if self.is_entry:
                            proc_res = self.anpr_processor.process_entry_event(
                                frame=frame, plate_crop=crop, temporal_result=temp_res, camera_id=cam_id
                            )
                        else:
                            proc_res = self.anpr_processor.process_exit_event(
                                frame=frame, plate_crop=crop, temporal_result=temp_res, camera_id=cam_id
                            )

                        with self.status_lock:
                            self.live_status["auth_status"] = proc_res.get("auth_status", "NOT REGISTERED")
                            self.live_status["access_decision"] = proc_res.get("access_decision", "ACCESS DENIED")
                            self.live_status["gate_status"] = proc_res.get("gate_status", "CLOSED")

            self.ocr_queue.task_done()

    def read_frame(self):
        """Thread-safe retrieval of latest frame."""
        if not self._running:
            self.start()

        if self.latest_annotated_frame is not None:
            return self.latest_annotated_frame
        elif self.latest_raw_frame is not None:
            return self.latest_raw_frame
        elif self.is_simulated:
            return self._generate_simulated_frame()
        return self._generate_disconnected_frame()

    def get_status_dict(self):
        """Returns snapshot of current live camera & recognition status for UI polling."""
        with self.status_lock:
            current_gate_stat = gate_controller.entry_gate_status if self.is_entry else gate_controller.exit_gate_status
            self.live_status["gate_status"] = current_gate_stat
            return dict(self.live_status)

    def generate_mjpeg_stream(self, fps=25):
        """Generator function producing MJPEG video frames for HTTP responses."""
        if not self._running:
            self.start()

        delay = 1.0 / fps
        while True:
            display_frame = self.read_frame()
            if display_frame is None:
                display_frame = self._generate_simulated_frame()

            ret, jpeg = cv2.imencode('.jpg', display_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(delay)


