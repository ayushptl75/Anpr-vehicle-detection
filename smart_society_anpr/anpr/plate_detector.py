import cv2
import numpy as np
import os
from config import (
    PLATE_MODEL_PATH, PLATE_CONFIDENCE_THRESHOLD,
    MIN_PLATE_WIDTH, MIN_PLATE_HEIGHT,
    MIN_PLATE_ASPECT_RATIO, MAX_PLATE_ASPECT_RATIO
)

try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
except ImportError:
    HAS_ULTRALYTICS = False


def letterbox_transform(image, target_size=(640, 640)):
    """
    Resizes image to target_size while preserving aspect ratio using padding.
    Returns:
        padded_img (numpy.ndarray): Resized and padded image
        scale (float): Scaling factor used
        pad_x (int): Horizontal padding offset
        pad_y (int): Vertical padding offset
    """
    orig_h, orig_w = image.shape[:2]
    target_w, target_h = target_size

    scale = min(target_w / float(orig_w), target_h / float(orig_h))
    new_w = int(round(orig_w * scale))
    new_h = int(round(orig_h * scale))

    pad_x = (target_w - new_w) // 2
    pad_y = (target_h - new_h) // 2

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    padded_img = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    padded_img[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    return padded_img, scale, pad_x, pad_y


def map_box_to_original(mx1, my1, mx2, my2, scale, pad_x, pad_y, orig_w, orig_h):
    """
    Converts detection box coordinates from resized/letterboxed space back to original camera resolution.
    Clips coordinates to valid original frame dimensions [0, orig_w - 1] and [0, orig_h - 1].
    """
    ox1 = (mx1 - pad_x) / scale
    oy1 = (my1 - pad_y) / scale
    ox2 = (mx2 - pad_x) / scale
    oy2 = (my2 - pad_y) / scale

    # Clip to original image boundaries
    ox1 = max(0, min(orig_w - 1, int(round(ox1))))
    oy1 = max(0, min(orig_h - 1, int(round(oy1))))
    ox2 = max(0, min(orig_w - 1, int(round(ox2))))
    oy2 = max(0, min(orig_h - 1, int(round(oy2))))

    # Ensure box coordinates are valid rectangles
    if ox2 <= ox1 or oy2 <= oy1:
        return None

    return ox1, oy1, ox2, oy2


class PlateDetector:
    def __init__(self, model_path=PLATE_MODEL_PATH, conf_threshold=PLATE_CONFIDENCE_THRESHOLD):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.model = None

        if HAS_ULTRALYTICS and os.path.exists(self.model_path):
            try:
                self.model = YOLO(self.model_path)
                print(f"[PlateDetector] Dedicated license plate model loaded: {self.model_path}")
            except Exception as e:
                print(f"[PlateDetector Error] Failed to load YOLO model: {e}")
                self.model = None
        else:
            print("[PlateDetector Info] Dedicated plate model weights file not found. Using high-precision OpenCV contour fallback detector.")

    def is_valid_plate_box(self, x1, y1, x2, y2, conf):
        """Validates bounding box dimensions, area, confidence, and aspect ratio."""
        if conf < self.conf_threshold:
            return False

        w = x2 - x1
        h = y2 - y1

        if w < MIN_PLATE_WIDTH or h < MIN_PLATE_HEIGHT:
            return False

        aspect_ratio = float(w) / float(h)
        if aspect_ratio < MIN_PLATE_ASPECT_RATIO or aspect_ratio > MAX_PLATE_ASPECT_RATIO:
            return False

        return True

    def detect(self, frame):
        """
        Detects license plates in the input camera frame.
        Handles arbitrary camera resolutions (1920x1080, 1280x720, 640x480, etc.).
        Returns list of detection dicts with coordinates strictly mapped to the ORIGINAL camera resolution.
        """
        if frame is None or frame.size == 0:
            return []

        orig_h, orig_w = frame.shape[:2]
        detections = []

        # Strategy 1: Dedicated YOLO License Plate Model (with Letterbox coordinate transform)
        if self.model is not None:
            target_size = (640, 640)
            letterboxed, scale, pad_x, pad_y = letterbox_transform(frame, target_size=target_size)
            
            results = self.model(letterboxed, verbose=False)[0]
            
            if results.boxes is not None and len(results.boxes) > 0:
                for box in results.boxes:
                    conf = float(box.conf[0].cpu().item())
                    mx1, my1, mx2, my2 = map(float, box.xyxy[0].cpu().tolist())
                    
                    orig_coords = map_box_to_original(mx1, my1, mx2, my2, scale, pad_x, pad_y, orig_w, orig_h)
                    if orig_coords is None:
                        continue
                    
                    ox1, oy1, ox2, oy2 = orig_coords
                    
                    if self.is_valid_plate_box(ox1, oy1, ox2, oy2, conf):
                        crop = frame[oy1:oy2, ox1:ox2].copy()
                        detections.append({
                            "x1": ox1,
                            "y1": oy1,
                            "x2": ox2,
                            "y2": oy2,
                            "confidence": conf,
                            "crop": crop
                        })
            return detections

        # Strategy 2: High-Precision Contour & Aspect Ratio Fallback Detector
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        sobelx = cv2.Sobel(blur, cv2.CV_8U, 1, 0, ksize=3)
        _, thresh = cv2.threshold(sobelx, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            ox1, oy1, ox2, oy2 = x, y, x + w, y + h
            
            # Simulated confidence for OpenCV fallback
            conf = 0.85
            
            if self.is_valid_plate_box(ox1, oy1, ox2, oy2, conf):
                crop = frame[oy1:oy2, ox1:ox2].copy()
                detections.append({
                    "x1": ox1,
                    "y1": oy1,
                    "x2": ox2,
                    "y2": oy2,
                    "confidence": conf,
                    "crop": crop
                })

        # Sort detections by area descending
        detections.sort(key=lambda d: (d["x2"] - d["x1"]) * (d["y2"] - d["y1"]), reverse=True)
        return detections

    def draw_detections(self, frame, plate_detections, vehicle_detections=None):
        """
        Draws bounding box annotations on the ORIGINAL camera frame.
        Yellow box for License Plates. Green box for Vehicles.
        """
        if frame is None:
            return frame

        annotated = frame.copy()

        # Draw Vehicle Boxes (Green) if present
        if vehicle_detections:
            for v in vehicle_detections:
                vx1, vy1, vx2, vy2 = v["x1"], v["y1"], v["x2"], v["y2"]
                cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), (0, 255, 0), 2)
                label = f"VEHICLE {v.get('confidence', 0.0):.2f}"
                cv2.putText(annotated, label, (vx1, max(15, vy1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Draw License Plate Boxes (Yellow box + Temporal Recognition & Gate Authorization badge)
        for p in plate_detections:
            px1, py1, px2, py2 = p["x1"], p["y1"], p["x2"], p["y2"]
            det_conf = p.get("confidence", 0.0)
            ocr_info = p.get("ocr_info", {})
            temp_info = p.get("temporal_info", {})
            gate_info = p.get("gate_info", {})
            
            plate_num = temp_info.get("plate_number") or ocr_info.get("plate_number", "")
            ocr_conf = temp_info.get("ocr_confidence") or ocr_info.get("ocr_confidence", 0.0)
            rec_status = temp_info.get("status", "SEARCHING")
            
            # Yellow bounding box for license plate
            cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 255), 2)
            
            if rec_status == "CONFIRMED" and gate_info and gate_info.get("access_decision") != "PENDING":
                auth_stat = gate_info.get("auth_status", "NOT REGISTERED")
                access_dec = gate_info.get("access_decision", "ACCESS DENIED")
                gate_stat = gate_info.get("gate_status", "CLOSED")
                res_name = gate_info.get("resident_name", "")
                
                if access_dec == "ACCESS ALLOWED":
                    label = f"CONFIRMED: {plate_num} | {auth_stat} | ACCESS ALLOWED | GATE OPEN ({res_name})"
                    badge_bg = (34, 197, 94)    # Green
                    text_color = (255, 255, 255)
                else:
                    label = f"CONFIRMED: {plate_num} | {auth_stat} | ACCESS DENIED | GATE CLOSED"
                    badge_bg = (239, 68, 68)    # Red
                    text_color = (255, 255, 255)
            elif plate_num:
                label = f"{rec_status} | {plate_num} ({ocr_conf:.2f})"
                if rec_status == "CONFIRMING":
                    badge_bg = (248, 189, 56)   # Blue/Cyan
                    text_color = (0, 0, 0)
                else: # SEARCHING
                    badge_bg = (30, 144, 255)   # Orange/Yellow
                    text_color = (255, 255, 255)
            else:
                label = f"SEARCHING... ({det_conf:.2f})"
                badge_bg = (0, 255, 255)
                text_color = (0, 0, 0)
            
            # Label background box
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            bg_y1 = max(0, py1 - h - 8)
            cv2.rectangle(annotated, (px1, bg_y1), (px1 + w + 8, py1), badge_bg, -1)
            cv2.putText(annotated, label, (px1 + 4, max(h, py1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, text_color, 2)

        return annotated
