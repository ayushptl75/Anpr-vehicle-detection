import unittest
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import (
    init_db, add_vehicle, get_db, create_gate_event,
    get_gate_events, get_day_summary, get_vehicles_inside_count
)
from gate.gate_controller import gate_controller
from anpr.processor import ANPRProcessor

class TestGateEventsDatabase(unittest.TestCase):

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

    def test_create_and_get_gate_events(self):
        event1 = create_gate_event(
            plate_number="GJ05 AB 1234",
            event_type="ENTRY",
            gate="ENTRY_GATE",
            camera_id="ENTRY_CAM_1",
            vehicle_image_path="/storage/entry/test_v1.jpg",
            plate_image_path="/storage/plates/test_p1.jpg",
            ocr_confidence=0.96,
            access_status="ALLOWED",
            event_date="2026-09-09",
            event_time="10:15:30"
        )
        self.assertIsNotNone(event1["id"])
        self.assertEqual(event1["plate_number"], "GJ05AB1234")
        self.assertEqual(event1["event_type"], "ENTRY")

        event2 = create_gate_event(
            plate_number="GJ05 AB 1234",
            event_type="EXIT",
            gate="EXIT_GATE",
            camera_id="EXIT_CAM_1",
            vehicle_image_path="/storage/exit/test_v2.jpg",
            plate_image_path="/storage/plates/test_p2.jpg",
            ocr_confidence=0.94,
            access_status="ALLOWED",
            event_date="2026-09-09",
            event_time="16:45:12"
        )
        self.assertIsNotNone(event2["id"])

        events_day = get_gate_events(date_str="2026-09-09")
        self.assertEqual(len(events_day), 2)

        # Test filtering by event type
        entry_events = get_gate_events(date_str="2026-09-09", event_type="ENTRY")
        self.assertEqual(len(entry_events), 1)
        self.assertEqual(entry_events[0]["event_type"], "ENTRY")

        exit_events = get_gate_events(date_str="2026-09-09", event_type="EXIT")
        self.assertEqual(len(exit_events), 1)
        self.assertEqual(exit_events[0]["event_type"], "EXIT")

    def test_day_wise_summary(self):
        # 2 Allowed Entries, 1 Denied Entry, 1 Allowed Exit for 2026-09-09
        create_gate_event("GJ05AB1234", "ENTRY", "ENTRY_GATE", "ENTRY_CAM", "/img/v1.jpg", "/img/p1.jpg", 0.95, "ALLOWED", "2026-09-09", "08:00:00")
        create_gate_event("MH12DE1432", "ENTRY", "ENTRY_GATE", "ENTRY_CAM", "/img/v2.jpg", "/img/p2.jpg", 0.92, "ALLOWED", "2026-09-09", "09:30:00")
        create_gate_event("KA99ZZ0000", "ENTRY", "ENTRY_GATE", "ENTRY_CAM", "/img/v3.jpg", "/img/p3.jpg", 0.85, "DENIED",  "2026-09-09", "10:00:00")
        create_gate_event("GJ05AB1234", "EXIT",  "EXIT_GATE",  "EXIT_CAM",  "/img/v4.jpg", "/img/p4.jpg", 0.94, "ALLOWED", "2026-09-09", "18:00:00")

        summary = get_day_summary("2026-09-09")
        self.assertEqual(summary["date"], "2026-09-09")
        self.assertEqual(summary["entries"], 2)
        self.assertEqual(summary["exits"], 1)

    def test_anpr_processor_automatic_gate_events_logging(self):
        processor = ANPRProcessor(cooldown_sec=10.0)

        # Register vehicle
        add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "ACTIVE")

        synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
        temporal_result = {
            "plate_number": "MH12DE1432",
            "ocr_confidence": 0.97,
            "status": "CONFIRMED"
        }

        # Process Entry
        processor.process_entry_event(synthetic_frame, synthetic_crop, temporal_result, camera_id="ENTRY_CAM_1")
        
        # Verify gate_events table populated
        events = get_gate_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["plate_number"], "MH12DE1432")
        self.assertEqual(events[0]["event_type"], "ENTRY")
        self.assertEqual(events[0]["access_status"], "ALLOWED")
        self.assertEqual(events[0]["gate"], "ENTRY_GATE")

        # Process Exit
        processor.process_exit_event(synthetic_frame, synthetic_crop, temporal_result, camera_id="EXIT_CAM_1")
        
        events = get_gate_events()
        self.assertEqual(len(events), 2)
        latest_event = events[0]
        self.assertEqual(latest_event["plate_number"], "MH12DE1432")
        self.assertEqual(latest_event["event_type"], "EXIT")
        self.assertEqual(latest_event["access_status"], "ALLOWED")
        self.assertEqual(latest_event["gate"], "EXIT_GATE")

if __name__ == '__main__':
    unittest.main()
