import unittest
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import (
    init_db, add_vehicle, get_db, get_vehicles_inside_count,
    is_vehicle_inside, get_access_logs
)
from gate.gate_controller import gate_controller
from anpr.processor import ANPRProcessor

class TestExitWorkflow(unittest.TestCase):

    def setUp(self):
        init_db()
        gate_controller.entry_gate_status = "CLOSED"
        gate_controller.exit_gate_status = "CLOSED"
        conn = get_db()
        conn.execute("DELETE FROM registered_vehicles")
        conn.execute("DELETE FROM access_logs")
        conn.commit()
        conn.close()

    def test_registered_vehicle_full_entry_exit_lifecycle(self):
        processor = ANPRProcessor(cooldown_sec=10.0)

        # 1. Add Active Registered Vehicle
        add_vehicle(
            plate_number="GJ05 AB 1234",
            resident_name="Rahul Patel",
            flat_number="A-101",
            vehicle_type="Car",
            status="ACTIVE"
        )
        self.assertEqual(get_vehicles_inside_count(), 0)

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        temporal_result = {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.95,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        # 2. Process ENTRY
        entry_res = processor.process_entry_event(
            frame=synthetic_frame,
            plate_crop=synthetic_crop,
            temporal_result=temporal_result,
            camera_id="ENTRY_CAM_1"
        )
        self.assertTrue(entry_res["success"])
        self.assertEqual(entry_res["access_decision"], "ACCESS ALLOWED")
        self.assertTrue(is_vehicle_inside("GJ05AB1234"))
        self.assertEqual(get_vehicles_inside_count(), 1)
        self.assertEqual(gate_controller.entry_gate_status, "OPEN")

        # Reset gate status for exit test
        gate_controller.exit_gate_status = "CLOSED"

        # 3. Process EXIT
        exit_res = processor.process_exit_event(
            frame=synthetic_frame,
            plate_crop=synthetic_crop,
            temporal_result=temporal_result,
            camera_id="EXIT_CAM_1"
        )
        self.assertTrue(exit_res["success"])
        self.assertEqual(exit_res["auth_status"], "REGISTERED")
        self.assertEqual(exit_res["access_decision"], "ACCESS ALLOWED")
        self.assertEqual(exit_res["gate_decision"], "GRANTED")
        self.assertEqual(exit_res["gate_status"], "OPEN")
        self.assertIsNotNone(exit_res["exit_image_path"])

        # 4. Verify DB updates & count decrement (1 -> 0)
        self.assertFalse(is_vehicle_inside("GJ05AB1234"))
        self.assertEqual(get_vehicles_inside_count(), 0)
        self.assertEqual(gate_controller.exit_gate_status, "OPEN")

        # Verify access_log status is COMPLETED
        logs = get_access_logs()
        matching = [l for l in logs if l["plate_number"] == "GJ05AB1234"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["status"], "COMPLETED")
        self.assertIsNotNone(matching[0]["exit_time"])

    def test_unregistered_vehicle_exit_workflow(self):
        processor = ANPRProcessor(cooldown_sec=10.0)
        self.assertEqual(get_vehicles_inside_count(), 0)

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)

        temporal_result = {
            "plate_number": "KA99ZZ0000",
            "ocr_confidence": 0.88,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        # Process EXIT for unregistered vehicle
        res = processor.process_exit_event(
            frame=synthetic_frame,
            plate_crop=synthetic_crop,
            temporal_result=temporal_result,
            camera_id="EXIT_CAM_1"
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["auth_status"], "NOT REGISTERED")
        self.assertEqual(res["access_decision"], "ACCESS DENIED")
        self.assertEqual(res["gate_decision"], "DENIED")
        self.assertEqual(res["gate_status"], "CLOSED")
        self.assertEqual(gate_controller.exit_gate_status, "CLOSED")
        self.assertEqual(get_vehicles_inside_count(), 0)

    def test_duplicate_exit_event_prevention(self):
        processor = ANPRProcessor(cooldown_sec=30.0)

        add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "ACTIVE")

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        temporal_result = {
            "plate_number": "MH12DE1432",
            "ocr_confidence": 0.95,
            "status": "CONFIRMED"
        }

        # Entry -> Inside count = 1
        processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertEqual(get_vehicles_inside_count(), 1)

        # First Exit event -> Inside count = 0
        exit_res1 = processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertTrue(exit_res1["success"])
        self.assertEqual(get_vehicles_inside_count(), 0)

        # Immediate Duplicate Exit Scan -> Prevented by Cooldown / Not Inside
        exit_res2 = processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertFalse(exit_res2["success"])
        self.assertTrue(exit_res2.get("duplicate", False))
        # Vehicle count must NOT be decreased below 0
        self.assertEqual(get_vehicles_inside_count(), 0)

if __name__ == '__main__':
    unittest.main()
