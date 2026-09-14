import unittest
import os
import sys
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from anpr.plate_detector import (
    PlateDetector, letterbox_transform, map_box_to_original
)

class TestPlateDetector(unittest.TestCase):

    def test_letterbox_transform_1080p(self):
        img_1080p = np.zeros((1080, 1920, 3), dtype=np.uint8)
        padded, scale, pad_x, pad_y = letterbox_transform(img_1080p, target_size=(640, 640))

        self.assertEqual(padded.shape, (640, 640, 3))
        expected_scale = 640.0 / 1920.0  # 0.333333
        self.assertAlmostEqual(scale, expected_scale, places=4)
        self.assertEqual(pad_x, 0)
        self.assertEqual(pad_y, 140)  # (640 - 1080 * (640/1920)) / 2 = (640 - 360)/2 = 140

    def test_map_box_to_original_accuracy(self):
        orig_w, orig_h = 1920, 1080
        img = np.zeros((orig_h, orig_w, 3), dtype=np.uint8)
        _, scale, pad_x, pad_y = letterbox_transform(img, target_size=(640, 640))

        # Simulate model detecting a plate at center of model input
        mx1, my1, mx2, my2 = 200, 200, 400, 250
        
        ox1, oy1, ox2, oy2 = map_box_to_original(mx1, my1, mx2, my2, scale, pad_x, pad_y, orig_w, orig_h)
        
        # Verify coordinates scale back to 1080p frame accurately
        self.assertTrue(0 <= ox1 < ox2 <= orig_w)
        self.assertTrue(0 <= oy1 < oy2 <= orig_h)
        
        # Test original coordinate recovery
        self.assertEqual(ox1, int(round((200 - pad_x) / scale)))
        self.assertEqual(oy1, int(round((200 - pad_y) / scale)))

    def test_coordinate_clipping_boundaries(self):
        orig_w, orig_h = 640, 480
        scale, pad_x, pad_y = 1.0, 0, 0
        
        # Out of bounds prediction (-50, -50, 800, 600)
        ox1, oy1, ox2, oy2 = map_box_to_original(-50, -50, 800, 600, scale, pad_x, pad_y, orig_w, orig_h)
        
        self.assertEqual(ox1, 0)
        self.assertEqual(oy1, 0)
        self.assertEqual(ox2, orig_w - 1)
        self.assertEqual(oy2, orig_h - 1)

    def test_filtering_rules(self):
        detector = PlateDetector(conf_threshold=0.25)
        
        # Valid plate box (200x50, aspect ratio 4.0, conf 0.9)
        self.assertTrue(detector.is_valid_plate_box(100, 100, 300, 150, 0.90))

        # Low confidence (< 0.25) -> Reject
        self.assertFalse(detector.is_valid_plate_box(100, 100, 300, 150, 0.15))

        # Very small box (< 25px width) -> Reject
        self.assertFalse(detector.is_valid_plate_box(100, 100, 110, 105, 0.90))

        # Square box (aspect ratio 1.0) -> Reject
        self.assertFalse(detector.is_valid_plate_box(100, 100, 150, 150, 0.90))

        # Ultra-wide box (aspect ratio 12.0) -> Reject
        self.assertFalse(detector.is_valid_plate_box(100, 100, 700, 150, 0.90))

    def test_detect_returns_correct_original_frame_coords(self):
        detector = PlateDetector()
        
        # Test on 1280x720 frame with synthetic plate region drawn
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(frame, (400, 500), (600, 550), (255, 255, 255), -1)
        
        detections = detector.detect(frame)
        self.assertIsInstance(detections, list)
        
        if len(detections) > 0:
            det = detections[0]
            self.assertIn("x1", det)
            self.assertIn("y1", det)
            self.assertIn("x2", det)
            self.assertIn("y2", det)
            self.assertIn("confidence", det)
            
            # Check coordinates strictly stay within frame
            self.assertTrue(0 <= det["x1"] < det["x2"] <= 1280)
            self.assertTrue(0 <= det["y1"] < det["y2"] <= 720)

    def test_draw_detections(self):
        detector = PlateDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        plates = [{"x1": 100, "y1": 100, "x2": 250, "y2": 140, "confidence": 0.92}]
        vehicles = [{"x1": 50, "y1": 50, "x2": 450, "y2": 350, "confidence": 0.88}]
        
        annotated = detector.draw_detections(frame, plates, vehicles)
        self.assertEqual(annotated.shape, frame.shape)

if __name__ == '__main__':
    unittest.main()
