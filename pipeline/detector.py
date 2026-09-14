import cv2
import numpy as np

class PlateDetector:
    def __init__(self):
        # Try loading default OpenCV plate cascade if available in cv2 build
        self.cascade = None
        if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):
            try:
                self.cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_russian_plate_number.xml")
            except Exception:
                self.cascade = None

    def detect_plate(self, frame):
        """
        Detects license plate ROI in a video frame.
        Returns:
            annotated_frame (numpy.ndarray): Frame with bounding box overlay
            plate_crop (numpy.ndarray or None): Cropped plate image ROI
            bbox (tuple or None): (x, y, w, h) bounding box coordinates
        """
        if frame is None:
            return None, None, None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        annotated_frame = frame.copy()
        plate_crop = None
        bbox = None

        # Method 1: Haar Cascade detection
        if self.cascade is not None and not self.cascade.empty():
            plates = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 20))
            if len(plates) > 0:
                # Select largest candidate by area
                plates = sorted(plates, key=lambda b: b[2] * b[3], reverse=True)
                x, y, w, h = plates[0]
                bbox = (x, y, w, h)
                plate_crop = frame[y:y+h, x:x+w]
                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                return annotated_frame, plate_crop, bbox

        # Method 2: OpenCV Contour & Aspect Ratio Fallback Detection
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        sobelx = cv2.Sobel(blur, cv2.CV_8U, 1, 0, ksize=3)
        _, thresh = cv2.threshold(sobelx, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        element = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, element)
        
        contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        candidates = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            aspect_ratio = float(w) / float(h)
            area = w * h
            
            # License plates typically have aspect ratio between 2.0 and 6.0
            if 2.0 <= aspect_ratio <= 6.5 and area > 1000 and area < (frame.shape[0] * frame.shape[1] * 0.2):
                candidates.append((x, y, w, h))

        if candidates:
            # Pick largest rectangular region
            candidates = sorted(candidates, key=lambda b: b[2] * b[3], reverse=True)
            x, y, w, h = candidates[0]
            bbox = (x, y, w, h)
            plate_crop = frame[y:y+h, x:x+w]
            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            return annotated_frame, plate_crop, bbox

        return annotated_frame, None, None
