import cv2
import numpy as np
import re

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

# Indian License Plate Validation Patterns
# Standard: 2 State Letters + 2 District Digits + 1-3 Series Letters + 4 Digits (e.g. MH12DE1432, GJ05AB1234, KA01C9999)
INDIAN_STANDARD_PATTERN = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$')
# Bharat (BH) Series: 2 Year Digits + BH + 4 Digits + 1-2 Letters (e.g. 22BH1234AA)
INDIAN_BHARAT_PATTERN = re.compile(r'^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$')


def crop_with_padding(frame, bbox, pad_pct=0.05):
    """
    Crops the license plate ROI from the frame with controlled padding percentage.
    Prevents modifying or destroying the original frame.
    """
    if frame is None or frame.size == 0 or not bbox:
        return None

    x1, y1, x2, y2 = bbox
    orig_h, orig_w = frame.shape[:2]

    w = x2 - x1
    h = y2 - y1

    px = int(round(w * pad_pct))
    py = int(round(h * pad_pct))

    cx1 = max(0, x1 - px)
    cy1 = max(0, y1 - py)
    cx2 = min(orig_w, x2 + px)
    cy2 = min(orig_h, y2 + py)

    if cx2 <= cx1 or cy2 <= cy1:
        return None

    return frame[cy1:cy2, cx1:cx2].copy()


def preprocess_variants(plate_crop, target_h=120):
    """
    Generates multiple image preprocessing variants for OCR to maximize recognition accuracy.
    Do not destroy original crop.
    """
    if plate_crop is None or plate_crop.size == 0:
        return []

    variants = []
    h, w = plate_crop.shape[:2]
    if h == 0 or w == 0:
        return []

    # Calculate resized dimensions
    scale = target_h / float(h)
    target_w = max(1, int(round(w * scale)))
    
    # 1. Color Resized Variant
    resized_color = cv2.resize(plate_crop, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
    variants.append(("color_resized", resized_color))

    # Convert to Grayscale
    gray = cv2.cvtColor(resized_color, cv2.COLOR_BGR2GRAY) if len(resized_color.shape) == 3 else resized_color.copy()

    # 2. Grayscale + Bilateral Filter (Noise Reduction) + CLAHE Contrast Enhancement
    denoised = cv2.bilateralFilter(gray, 11, 17, 17)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    variants.append(("clahe_contrast", enhanced))

    # 3. Adaptive Otsu Threshold Binarization
    _, otsu_thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("otsu_thresh", otsu_thresh))

    return variants


def normalize_text(raw_text: str) -> str:
    """
    Normalizes OCR raw text: converts to uppercase, removes spaces, hyphens, and punctuation.
    """
    if not raw_text:
        return ""
    return re.sub(r'[^A-Z0-9]', '', raw_text.upper())


def validate_indian_plate(plate_text: str) -> str:
    """
    Validates license plate string against Indian registration format patterns.
    Returns 'VALID_INDIAN_PLATE' or 'INVALID_FORMAT'.
    """
    if not plate_text:
        return "INVALID_FORMAT"

    clean_text = normalize_text(plate_text)

    if INDIAN_STANDARD_PATTERN.match(clean_text) or INDIAN_BHARAT_PATTERN.match(clean_text):
        return "VALID_INDIAN_PLATE"
    
    return "INVALID_FORMAT"


class PlateOCR:
    def __init__(self, use_gpu=False):
        self.reader = None
        self.has_easyocr = HAS_EASYOCR
        if self.has_easyocr:
            try:
                self.reader = easyocr.Reader(['en'], gpu=use_gpu)
                print("[PlateOCR] EasyOCR Reader initialized successfully.")
            except Exception as e:
                print(f"[PlateOCR Error] Failed to initialize EasyOCR: {e}")
                self.has_easyocr = False

    def read_plate(self, plate_crop):
        """
        Runs full OCR recognition pipeline on plate_crop using multiple preprocessing variants.
        Returns dict:
        {
            "plate_number": str,
            "ocr_confidence": float,
            "validation_status": str ("VALID_INDIAN_PLATE" | "INVALID_FORMAT")
        }
        """
        if plate_crop is None or plate_crop.size == 0:
            return {
                "plate_number": "",
                "ocr_confidence": 0.0,
                "validation_status": "INVALID_FORMAT"
            }

        variants = preprocess_variants(plate_crop)
        candidates = []

        if self.has_easyocr and self.reader is not None:
            for v_name, v_img in variants:
                try:
                    results = self.reader.readtext(v_img, detail=1, paragraph=False)
                    for bbox, text, conf in results:
                        clean = normalize_text(text)
                        if len(clean) >= 4:
                            val_status = validate_indian_plate(clean)
                            candidates.append({
                                "plate_number": clean,
                                "ocr_confidence": round(float(conf), 4),
                                "validation_status": val_status,
                                "variant": v_name
                            })
                except Exception as e:
                    print(f"[PlateOCR Warning] EasyOCR error on variant {v_name}: {e}")

        # Pick best candidate: Prioritize VALID_INDIAN_PLATE first, then highest confidence
        if candidates:
            valid_candidates = [c for c in candidates if c["validation_status"] == "VALID_INDIAN_PLATE"]
            if valid_candidates:
                best = max(valid_candidates, key=lambda c: c["ocr_confidence"])
            else:
                best = max(candidates, key=lambda c: c["ocr_confidence"])

            return {
                "plate_number": best["plate_number"],
                "ocr_confidence": best["ocr_confidence"],
                "validation_status": best["validation_status"]
            }

        return {
            "plate_number": "",
            "ocr_confidence": 0.0,
            "validation_status": "INVALID_FORMAT"
        }
