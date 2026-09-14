import unittest
import os
import sys
import time
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import ENTRY_CAMERA_URL, EXIT_CAMERA_URL
from database.database import (
    init_db, add_vehicle, edit_vehicle, deactivate_vehicle, search_vehicles, list_vehicles,
    get_db, get_vehicles_inside_count, get_vehicles_inside_list, is_vehicle_inside,
    get_gate_events, create_gate_event, get_day_summary, get_report_records
)
from gate.gate_controller import gate_controller
from anpr.camera import CameraService
from anpr.plate_detector import PlateDetector
from anpr.ocr import PlateOCR
from anpr.recognizer import MultiFrameRecognizer
from anpr.processor import ANPRProcessor
from reports.report_service import report_service

class TestSystemFullPhase14(unittest.TestCase):

    def setUp(self):
        init_db()
        gate_controller.entry_gate_status = "CLOSED"
        gate_controller.exit_gate_status = "CLOSED"
        conn = get_db()
        conn.execute("DELETE FROM registered_vehicles")
        conn.execute("DELETE FROM access_logs")
        conn.execute("DELETE FROM gate_events")
        conn.commit()
        conn.close()

    # 1. Live entry camera
    def test_01_live_entry_camera(self):
        cam = CameraService(camera_url=ENTRY_CAMERA_URL, name="Test Entry Cam", is_entry=True)
        cam.start()
        time.sleep(0.2)
        frame = cam.read_frame()
        self.assertIsNotNone(frame)
        self.assertIsInstance(frame, np.ndarray)
        cam.stop()

    # 2. Live exit camera
    def test_02_live_exit_camera(self):
        cam = CameraService(camera_url=EXIT_CAMERA_URL, name="Test Exit Cam", is_entry=False)
        cam.start()
        time.sleep(0.2)
        frame = cam.read_frame()
        self.assertIsNotNone(frame)
        self.assertIsInstance(frame, np.ndarray)
        cam.stop()

    # 3. Registered vehicle
    def test_03_registered_vehicle(self):
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        auth = gate_controller.evaluate_access("GJ05AB1234")
        self.assertEqual(auth["auth_status"], "REGISTERED")
        self.assertEqual(auth["access_decision"], "ACCESS ALLOWED")

    # 4. Unregistered vehicle
    def test_04_unregistered_vehicle(self):
        auth = gate_controller.evaluate_access("KA99ZZ0000")
        self.assertEqual(auth["auth_status"], "NOT REGISTERED")
        self.assertEqual(auth["access_decision"], "ACCESS DENIED")

    # 5. Accurate plate detection
    def test_05_accurate_plate_detection(self):
        detector = PlateDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[200:260, 240:400] = 255
        dets = detector.detect(frame)
        self.assertIsInstance(dets, list)

    # 6. Incorrect OCR frame
    def test_06_incorrect_ocr_frame_rejection(self):
        rec = MultiFrameRecognizer(min_reads=3)
        bbox = (10, 10, 100, 50)
        rec.process_observation(bbox, {"plate_number": "GJ05AB1234", "ocr_confidence": 0.95, "validation_status": "VALID_INDIAN_PLATE"})
        rec.process_observation(bbox, {"plate_number": "GJ05AB1234", "ocr_confidence": 0.96, "validation_status": "VALID_INDIAN_PLATE"})
        rec.process_observation(bbox, {"plate_number": "GJ05A8134",  "ocr_confidence": 0.60, "validation_status": "INVALID_FORMAT"})
        result = rec.process_observation(bbox, {"plate_number": "GJ05AB1234", "ocr_confidence": 0.94, "validation_status": "VALID_INDIAN_PLATE"})
        
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["plate_number"], "GJ05AB1234")

    # 7. Multi-frame confirmation
    def test_07_multi_frame_confirmation(self):
        rec = MultiFrameRecognizer(min_reads=3)
        bbox = (10, 10, 100, 50)
        res1 = rec.process_observation(bbox, {"plate_number": "MH12DE1432", "ocr_confidence": 0.91, "validation_status": "VALID_INDIAN_PLATE"})
        self.assertEqual(res1["status"], "SEARCHING")
        res2 = rec.process_observation(bbox, {"plate_number": "MH12DE1432", "ocr_confidence": 0.93, "validation_status": "VALID_INDIAN_PLATE"})
        self.assertEqual(res2["status"], "CONFIRMING")
        res3 = rec.process_observation(bbox, {"plate_number": "MH12DE1432", "ocr_confidence": 0.95, "validation_status": "VALID_INDIAN_PLATE"})
        self.assertEqual(res3["status"], "CONFIRMED")

    # 8. Duplicate vehicle detection
    def test_08_duplicate_vehicle_detection(self):
        processor = ANPRProcessor(cooldown_sec=30.0)
        add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "ACTIVE")
        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        temporal_result = {"plate_number": "MH12DE1432", "ocr_confidence": 0.95, "status": "CONFIRMED"}

        res1 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertTrue(res1["success"])
        res2 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertFalse(res2["success"])
        self.assertTrue(res2.get("duplicate", False))

    # 9. Entry event
    def test_09_entry_event(self):
        processor = ANPRProcessor()
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        temporal_result = {"plate_number": "GJ05AB1234", "ocr_confidence": 0.95, "status": "CONFIRMED"}

        res = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result, camera_id="ENTRY_CAM_1")
        self.assertTrue(res["success"])
        self.assertEqual(res["gate_decision"], "GRANTED")
        self.assertTrue(is_vehicle_inside("GJ05AB1234"))

    # 10. Exit event
    def test_10_exit_event(self):
        processor = ANPRProcessor()
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        temporal_result = {"plate_number": "GJ05AB1234", "ocr_confidence": 0.95, "status": "CONFIRMED"}

        processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertEqual(get_vehicles_inside_count(), 1)

        exit_res = processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result, camera_id="EXIT_CAM_1")
        self.assertTrue(exit_res["success"])
        self.assertEqual(get_vehicles_inside_count(), 0)

    # 11. Vehicle count
    def test_11_vehicle_count_consistency(self):
        self.assertEqual(get_vehicles_inside_count(), 0)
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        temporal_result = {"plate_number": "GJ05AB1234", "ocr_confidence": 0.95, "status": "CONFIRMED"}

        processor = ANPRProcessor()
        processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertEqual(get_vehicles_inside_count(), 1)
        processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertEqual(get_vehicles_inside_count(), 0)

    # 12. Camera disconnect
    def test_12_camera_disconnect(self):
        cam = CameraService(camera_url="invalid_cam_999", name="Offline Cam")
        cam.start()
        time.sleep(0.2)
        frame = cam.read_frame()
        self.assertIsNotNone(frame)
        cam.stop()

    # 13. Camera reconnect
    def test_13_camera_reconnect(self):
        cam = CameraService(camera_url=0, name="Reconnect Cam")
        cam.start()
        time.sleep(0.1)
        self.assertTrue(cam.is_running)
        cam.stop()
        self.assertFalse(cam.is_running)

    # 14. Different camera resolutions
    def test_14_different_camera_resolutions(self):
        detector = PlateDetector()
        resolutions = [(640, 480), (1280, 720), (1920, 1080), (3840, 2160)]
        for w, h in resolutions:
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[int(h*0.4):int(h*0.5), int(w*0.4):int(w*0.6)] = 255
            dets = detector.detect(frame)
            self.assertIsInstance(dets, list)
            for d in dets:
                self.assertTrue(0 <= d["x1"] <= w)
                self.assertTrue(0 <= d["y1"] <= h)
                self.assertTrue(0 <= d["x2"] <= w)
                self.assertTrue(0 <= d["y2"] <= h)

    # 15. Multiple vehicles
    def test_15_multiple_vehicles(self):
        processor = ANPRProcessor()
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "ACTIVE")

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)

        processor.process_entry_event(synthetic_frame, synthetic_crop, {"plate_number": "GJ05AB1234", "ocr_confidence": 0.95, "status": "CONFIRMED"})
        processor.process_entry_event(synthetic_frame, synthetic_crop, {"plate_number": "MH12DE1432", "ocr_confidence": 0.96, "status": "CONFIRMED"})

        self.assertEqual(get_vehicles_inside_count(), 2)

    # 16. Day-wise records
    def test_16_day_wise_records(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        create_gate_event("GJ05AB1234", "ENTRY", "ENTRY_GATE", "ENTRY_CAM", "/v1.jpg", "/p1.jpg", 0.95, "ALLOWED", today_str, "10:00:00")
        events = get_gate_events(date_str=today_str)
        self.assertGreaterEqual(len(events), 1)

    # 17. Registered vehicle CRUD
    def test_17_registered_vehicle_crud(self):
        res_add = add_vehicle("DL08CA9999", "Alice Smith", "C-303", "Bike", "ACTIVE")
        self.assertTrue(res_add["success"])

        res_edit = edit_vehicle(res_add["id"], "Alice Smith Updated", "C-304", "Bike", "ACTIVE")
        self.assertTrue(res_edit["success"])

        res_deact = deactivate_vehicle(res_add["id"])
        self.assertTrue(res_deact["success"])

        vehicles = search_vehicles("DL08CA9999")
        self.assertEqual(len(vehicles), 1)
        self.assertEqual(vehicles[0]["status"], "INACTIVE")

    # 18. Reports
    def test_18_reports(self):
        report = report_service.generate_report(filter_type="today")
        self.assertIn("total_entries", report)
        self.assertIn("total_exits", report)
        self.assertIn("currently_inside", report)
        self.assertIn("denied_attempts", report)

        csv_data = report_service.export_csv(report)
        self.assertIn("SMART SOCIETY SECURITY GATE REPORT", csv_data)

if __name__ == '__main__':
    unittest.main()
