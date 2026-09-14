import unittest
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import (
    init_db, add_vehicle, get_db, get_vehicles_inside_count,
    get_vehicles_inside_list, is_vehicle_inside
)
from gate.gate_controller import gate_controller
from anpr.processor import ANPRProcessor

class TestVehicleInsideCounting(unittest.TestCase):

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

    def test_vehicle_inside_counting_lifecycle_and_edge_cases(self):
        processor = ANPRProcessor(cooldown_sec=10.0)

        # 0. Initial State Check
        self.assertEqual(get_vehicles_inside_count(), 0)
        self.assertEqual(len(get_vehicles_inside_list()), 0)

        # Register 2 active vehicles
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "ACTIVE")

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)

        temporal_result_1 = {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.96,
            "status": "CONFIRMED"
        }

        # Edge Case 1 & Rule 1: Confirmed Entry -> Count +1 (0 -> 1)
        res1 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result_1)
        self.assertTrue(res1["success"])
        self.assertEqual(get_vehicles_inside_count(), 1)
        inside_list = get_vehicles_inside_list()
        self.assertEqual(len(inside_list), 1)
        self.assertEqual(inside_list[0]["plate_number"], "GJ05AB1234")

        # Edge Case 1 & 2: Repeated detections of same vehicle at Entry (duplicate frame) -> Count MUST remain 1
        res1_dup1 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result_1)
        self.assertFalse(res1_dup1["success"])
        self.assertTrue(res1_dup1.get("duplicate", False))
        self.assertEqual(get_vehicles_inside_count(), 1)

        res1_dup2 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result_1)
        self.assertFalse(res1_dup2["success"])
        self.assertEqual(get_vehicles_inside_count(), 1)

        # Edge Case Denial: Unregistered vehicle scanned -> DENIED -> Count MUST remain 1
        unreg_temporal = {
            "plate_number": "KA99ZZ0000",
            "ocr_confidence": 0.89,
            "status": "CONFIRMED"
        }
        res_unreg = processor.process_entry_event(synthetic_frame, synthetic_crop, unreg_temporal)
        self.assertTrue(res_unreg["success"])
        self.assertEqual(res_unreg["access_decision"], "ACCESS DENIED")
        self.assertEqual(get_vehicles_inside_count(), 1)

        # Second Vehicle Entry -> Count +1 (1 -> 2)
        temporal_result_2 = {
            "plate_number": "MH12DE1432",
            "ocr_confidence": 0.95,
            "status": "CONFIRMED"
        }
        res2 = processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result_2)
        self.assertTrue(res2["success"])
        self.assertEqual(get_vehicles_inside_count(), 2)
        self.assertEqual(len(get_vehicles_inside_list()), 2)

        # Edge Case 3: Confirmed Exit of 1st vehicle -> Count -1 (2 -> 1)
        exit_res1 = processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result_1)
        self.assertTrue(exit_res1["success"])
        self.assertEqual(get_vehicles_inside_count(), 1)
        self.assertFalse(is_vehicle_inside("GJ05AB1234"))
        self.assertTrue(is_vehicle_inside("MH12DE1432"))

        # Edge Case 4: Duplicate Exit scan of 1st vehicle -> Count MUST remain 1
        exit_res1_dup = processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result_1)
        self.assertFalse(exit_res1_dup["success"])
        self.assertEqual(get_vehicles_inside_count(), 1)

        # Edge Case 5: Application Restart Simulation -> Count re-queried from database MUST remain 1
        self.assertEqual(get_vehicles_inside_count(), 1)
        inside_list_restarted = get_vehicles_inside_list()
        self.assertEqual(len(inside_list_restarted), 1)
        self.assertEqual(inside_list_restarted[0]["plate_number"], "MH12DE1432")

        # Exit 2nd vehicle -> Count -1 (1 -> 0)
        exit_res2 = processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result_2)
        self.assertTrue(exit_res2["success"])
        self.assertEqual(get_vehicles_inside_count(), 0)

        # Extra Exit scan when count is 0 -> Count MUST NEVER drop below 0
        exit_res2_dup = processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result_2)
        self.assertFalse(exit_res2_dup["success"])
        self.assertEqual(get_vehicles_inside_count(), 0)

if __name__ == '__main__':
    unittest.main()
