import unittest
import os
import sys
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import (
    init_db, add_vehicle, get_db, create_gate_event, get_report_records
)
from gate.gate_controller import gate_controller
from anpr.processor import ANPRProcessor
from reports.report_service import report_service

class TestDayWiseReports(unittest.TestCase):

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

    def test_report_generation_and_metrics(self):
        # Register vehicle
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")

        # Create entry event for 2026-09-09
        create_gate_event(
            plate_number="GJ05AB1234",
            event_type="ENTRY",
            gate="ENTRY_GATE",
            camera_id="ENTRY_CAM_1",
            vehicle_image_path="/storage/entry/test1.jpg",
            plate_image_path="/storage/plates/test1.jpg",
            ocr_confidence=0.96,
            access_status="ALLOWED",
            event_date="2026-09-09",
            event_time="10:15:30"
        )

        # Create exit event for 2026-09-09
        create_gate_event(
            plate_number="GJ05AB1234",
            event_type="EXIT",
            gate="EXIT_GATE",
            camera_id="EXIT_CAM_1",
            vehicle_image_path="/storage/exit/test2.jpg",
            plate_image_path="/storage/plates/test2.jpg",
            ocr_confidence=0.95,
            access_status="ALLOWED",
            event_date="2026-09-09",
            event_time="16:30:00"
        )

        # Create denied event for 2026-09-09
        create_gate_event(
            plate_number="KA99ZZ0000",
            event_type="ENTRY",
            gate="ENTRY_GATE",
            camera_id="ENTRY_CAM_1",
            vehicle_image_path="/storage/entry/test3.jpg",
            plate_image_path="/storage/plates/test3.jpg",
            ocr_confidence=0.88,
            access_status="DENIED",
            event_date="2026-09-09",
            event_time="11:00:00"
        )

        # Generate report for 2026-09-09
        report = report_service.generate_report(filter_type="specific", specific_date="2026-09-09")
        
        self.assertEqual(report["start_date"], "2026-09-09")
        self.assertEqual(report["total_entries"], 1)
        self.assertEqual(report["total_exits"], 1)
        self.assertEqual(report["denied_attempts"], 1)

    def test_export_formats(self):
        report_data = {
            "start_date": "2026-09-09",
            "end_date": "2026-09-09",
            "total_entries": 1,
            "total_exits": 1,
            "currently_inside": 0,
            "denied_attempts": 1,
            "records": [
                {
                    "plate_number": "GJ05AB1234",
                    "entry_date": "2026-09-09",
                    "entry_time": "10:15:30",
                    "exit_date": "2026-09-09",
                    "exit_time": "16:30:00",
                    "status": "COMPLETED"
                }
            ]
        }

        # CSV Export Test
        csv_out = report_service.export_csv(report_data)
        self.assertIn("SMART SOCIETY SECURITY GATE REPORT", csv_out)
        self.assertIn("GJ05AB1234", csv_out)
        self.assertIn("10:15:30", csv_out)

        # Excel Export Test
        excel_out = report_service.export_excel(report_data)
        self.assertIn("GJ05AB1234", excel_out)

        # PDF HTML Export Test
        pdf_out = report_service.export_pdf_html(report_data)
        self.assertIn("Smart Society Gate Access Report", pdf_out)
        self.assertIn("GJ05AB1234", pdf_out)
        self.assertIn("onload=\"window.print()\"", pdf_out)

if __name__ == '__main__':
    unittest.main()
