import unittest
import os
import sys
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from anpr.ocr import (
    PlateOCR, crop_with_padding, preprocess_variants,
    normalize_text, validate_indian_plate
)

class TestPlateOCR(unittest.TestCase):

    def test_normalize_text(self):
        self.assertEqual(normalize_text("mh-12 de 1432."), "MH12DE1432")
        self.assertEqual(normalize_text("gj 05.ab.1234"), "GJ05AB1234")
        self.assertEqual(normalize_text(" ka 01 - c - 9999 "), "KA01C9999")
        self.assertEqual(normalize_text(""), "")

    def test_validate_indian_plate_formats(self):
        # Valid Standard Indian Plates
        self.assertEqual(validate_indian_plate("MH12DE1432"), "VALID_INDIAN_PLATE")
        self.assertEqual(validate_indian_plate("GJ05AB1234"), "VALID_INDIAN_PLATE")
        self.assertEqual(validate_indian_plate("KA01C9999"), "VALID_INDIAN_PLATE")
        self.assertEqual(validate_indian_plate("DL08CA9999"), "VALID_INDIAN_PLATE")
        self.assertEqual(validate_indian_plate("TN09AX1234"), "VALID_INDIAN_PLATE")

        # Valid Bharat (BH) Series
        self.assertEqual(validate_indian_plate("22BH1234AA"), "VALID_INDIAN_PLATE")

        # Invalid Formats
        self.assertEqual(validate_indian_plate("INVALID123"), "INVALID_FORMAT")
        self.assertEqual(validate_indian_plate("12345"), "INVALID_FORMAT")
        self.assertEqual(validate_indian_plate("MH12"), "INVALID_FORMAT")
        self.assertEqual(validate_indian_plate("ABCDE123456"), "INVALID_FORMAT")

    def test_crop_with_padding(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        bbox = (100, 100, 200, 150)
        
        cropped = crop_with_padding(frame, bbox, pad_pct=0.10)
        self.assertIsNotNone(cropped)
        
        # Original width 100, pad 10px -> 120px
        # Original height 50, pad 5px -> 60px
        self.assertEqual(cropped.shape[0], 60)
        self.assertEqual(cropped.shape[1], 120)

    def test_preprocess_variants_generation(self):
        sample_crop = np.zeros((50, 200, 3), dtype=np.uint8)
        variants = preprocess_variants(sample_crop, target_h=120)
        
        self.assertEqual(len(variants), 3)
        variant_names = [v[0] for v in variants]
        self.assertIn("color_resized", variant_names)
        self.assertIn("clahe_contrast", variant_names)
        self.assertIn("otsu_thresh", variant_names)

    def test_read_plate_result_structure(self):
        ocr = PlateOCR()
        crop = np.zeros((50, 200, 3), dtype=np.uint8)
        
        result = ocr.read_plate(crop)
        self.assertIn("plate_number", result)
        self.assertIn("ocr_confidence", result)
        self.assertIn("validation_status", result)
        self.assertIsInstance(result["plate_number"], str)
        self.assertIsInstance(result["ocr_confidence"], float)
        self.assertIn(result["validation_status"], ["VALID_INDIAN_PLATE", "INVALID_FORMAT"])

if __name__ == '__main__':
    unittest.main()
