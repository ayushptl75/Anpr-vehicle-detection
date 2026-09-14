import cv2
import re
import os

try:
    import pytesseract
    from config import TESSERACT_CMD
    if os.path.exists(TESSERACT_CMD):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

class PlateOCR:
    def __init__(self):
        self.tesseract_available = HAS_TESSERACT

    def clean_text(self, raw_text: str) -> str:
        """Normalizes plate text: removes non-alphanumeric chars and converts to uppercase."""
        cleaned = re.sub(r'[^A-Z0-9]', '', raw_text.upper())
        return cleaned

    def extract_text(self, plate_crop) -> str:
        """
        Processes plate cropped image and extracts alphanumeric string.
        """
        if plate_crop is None or plate_crop.size == 0:
            return ""

        # Image Pre-processing for optimal OCR accuracy
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY) if len(plate_crop.shape) == 3 else plate_crop
        
        # Resize to standard height for OCR consistency
        h, w = gray.shape[:2]
        if h > 0:
            target_h = 100
            target_w = int(w * (target_h / float(h)))
            gray = cv2.resize(gray, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

        # Bilateral filter & Adaptive Thresholding
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)
        _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if self.tesseract_available:
            try:
                # PSM 7: Treat image as a single text line
                config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                text = pytesseract.image_to_string(thresh, config=config)
                cleaned = self.clean_text(text)
                if len(cleaned) >= 4:
                    return cleaned
                
                # Fallback PSM 8: Single word
                config_alt = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                text_alt = pytesseract.image_to_string(thresh, config=config_alt)
                cleaned_alt = self.clean_text(text_alt)
                if len(cleaned_alt) >= 4:
                    return cleaned_alt

                return cleaned
            except Exception as e:
                print(f"[OCR Warning] Tesseract error: {e}")
                return ""
        
        return ""
