import unittest
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from anpr.recognizer import MultiFrameRecognizer, calculate_iou

class TestMultiFrameRecognizer(unittest.TestCase):

    def test_calculate_iou(self):
        boxA = (100, 100, 200, 200)
        boxB = (150, 100, 250, 200)
        iou = calculate_iou(boxA, boxB)
        self.assertAlmostEqual(iou, 0.3333, places=3)

        # No overlap
        boxC = (300, 300, 400, 400)
        self.assertEqual(calculate_iou(boxA, boxC), 0.0)

    def test_multi_frame_voting_sequence_example(self):
        rec = MultiFrameRecognizer(min_reads=3, min_score=2.0)
        bbox = (100, 100, 250, 150)

        # Frame 1 → GJ05AB1234 → 92%
        res1 = rec.process_observation(bbox, {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.92,
            "validation_status": "VALID_INDIAN_PLATE"
        })
        self.assertEqual(res1["status"], "SEARCHING")
        self.assertEqual(res1["plate_number"], "GJ05AB1234")

        # Frame 2 → GJ05AB1234 → 95%
        res2 = rec.process_observation(bbox, {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.95,
            "validation_status": "VALID_INDIAN_PLATE"
        })
        self.assertEqual(res2["status"], "CONFIRMING")

        # Frame 3 → GJ05A8134 → 72% (Noise frame)
        res3 = rec.process_observation(bbox, {
            "plate_number": "GJ05A8134",
            "ocr_confidence": 0.72,
            "validation_status": "INVALID_FORMAT"
        })
        self.assertEqual(res3["status"], "CONFIRMING")
        # GJ05AB1234 remains top candidate due to higher confidence weight & valid status
        self.assertEqual(res3["plate_number"], "GJ05AB1234")

        # Frame 4 → GJ05AB1234 → 96%
        res4 = rec.process_observation(bbox, {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.96,
            "validation_status": "VALID_INDIAN_PLATE"
        })
        self.assertEqual(res4["status"], "CONFIRMED")
        self.assertEqual(res4["plate_number"], "GJ05AB1234")

        # Frame 5 → GJ05AB1234 → 94%
        res5 = rec.process_observation(bbox, {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.94,
            "validation_status": "VALID_INDIAN_PLATE"
        })
        self.assertEqual(res5["status"], "CONFIRMED")
        self.assertEqual(res5["plate_number"], "GJ05AB1234")

    def test_rejection_unstable_single_bad_frame(self):
        rec = MultiFrameRecognizer(min_reads=3, min_score=2.0)
        bbox = (100, 100, 250, 150)

        # Single bad frame reading false plate
        res = rec.process_observation(bbox, {
            "plate_number": "BADPLATE99",
            "ocr_confidence": 0.99,
            "validation_status": "INVALID_FORMAT"
        })
        self.assertNotEqual(res["status"], "CONFIRMED")

    def test_track_expiration(self):
        rec = MultiFrameRecognizer(expiry_sec=0.2)
        bbox = (100, 100, 250, 150)

        rec.process_observation(bbox, {
            "plate_number": "KA01AB9999",
            "ocr_confidence": 0.90,
            "validation_status": "VALID_INDIAN_PLATE"
        })
        self.assertEqual(len(rec.tracks), 1)

        # Wait for expiration
        time.sleep(0.25)
        rec.purge_stale_tracks()
        self.assertEqual(len(rec.tracks), 0)

if __name__ == '__main__':
    unittest.main()
