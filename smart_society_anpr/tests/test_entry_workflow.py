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

class TestEntryWorkflow(unittest.TestCase):

    def setUp(self):
        init_db()
        gate_controller.entry_gate_status = "CLOSED"
        gate_controller.exit_gate_status = "CLOSED"
        conn = get_db()
        conn.execute("DELETE FROM registered_vehicles")
        conn.execute("DELETE FROM access_logs")
        conn.commit()
        conn.close()

    def test_registered_active_vehicle_entry_workflow(self):
        processor = ANPRProcessor(cooldown_sec=10.0)

        # 1. Register Vehicle
        add_vehicle(
            plate_number="GJ05 AB 1234",
            resident_name="Rahul Patel",
            flat_number="A-101",
            vehicle_type="Car",
            status="ACTIVE"
        )
        self.assertEqual(get_vehicles_inside_count(), 0)

        # 2. Process Confirmed Entry Event
        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        
        temporal_result = {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.96,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        res = processor.process_entry_event(
            frame=synthetic_frame,
            plate_crop=synthetic_crop,
            temporal_result=temporal_result,
            camera_id="ENTRY_CAM_1"
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["auth_status"], "REGISTERED")
        self.assertEqual(res["access_decision"], "ACCESS ALLOWED")
        self.assertEqual(res["gate_decision"], "GRANTED")
        self.assertEqual(res["gate_status"], "OPEN")
        self.assertIsNotNone(res["entry_image_path"])
        self.assertIsNotNone(res["plate_image_path"])

        # Verify DB updates & count increment
        self.assertTrue(is_vehicle_inside("GJ05AB1234"))
        self.assertEqual(get_vehicles_inside_count(), 1)
        self.assertEqual(gate_controller.entry_gate_status, "OPEN")

    def test_unregistered_vehicle_entry_workflow(self):
        processor = ANPRProcessor(cooldown_sec=10.0)
        self.assertEqual(get_vehicles_inside_count(), 0)

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)

        temporal_result = {
            "plate_number": "KA99ZZ0000",
            "ocr_confidence": 0.91,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        res = processor.process_entry_event(
            frame=synthetic_frame,
            plate_crop=synthetic_crop,
            temporal_result=temporal_result,
            camera_id="ENTRY_CAM_1"
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["auth_status"], "NOT REGISTERED")
        self.assertEqual(res["access_decision"], "ACCESS DENIED")
        self.assertEqual(res["gate_decision"], "DENIED")
        self.assertEqual(res["gate_status"], "CLOSED")

        # Verify DB status DENIED & count NOT incremented
        self.assertFalse(is_vehicle_inside("KA99ZZ0000"))
        self.assertEqual(get_vehicles_inside_count(), 0)
        self.assertEqual(gate_controller.entry_gate_status, "CLOSED")

    def test_duplicate_entry_event_prevention(self):
        processor = ANPRProcessor(cooldown_sec=30.0)

        add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "ACTIVE")

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)

        temporal_result = {
            "plate_number": "MH12DE1432",
            "ocr_confidence": 0.95,
            "status": "CONFIRMED"
        }

        # First entry event -> SUCCESS
        res1 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertTrue(res1["success"])
        self.assertEqual(get_vehicles_inside_count(), 1)

        # Immediate consecutive frame 2 -> PREVENT DUPLICATE
        res2 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertFalse(res2["success"])
        self.assertTrue(res2["duplicate"])
        self.assertEqual(get_vehicles_inside_count(), 1)

        # Consecutive frame 3 -> PREVENT DUPLICATE
        res3 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result)
        self.assertFalse(res3["success"])
        self.assertTrue(res3["duplicate"])
        self.assertEqual(get_vehicles_inside_count(), 1)

        # Verify only 1 log entry created in DB for MH12DE1432
        logs = get_access_logs()
        mh12_logs = [l for l in logs if l["plate_number"] == "MH12DE1432"]
        self.assertEqual(len(mh12_logs), 1)

if __name__ == '__main__':
    unittest.main()
