import unittest
import os
import sys
import time
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import init_db, add_vehicle, get_db
from gate.hardware_controller import ArduinoHardwareController
from gate.gate_controller import GateController


class TestHardwareIntegration(unittest.TestCase):

    def setUp(self):
        init_db()
        conn = get_db()
        conn.execute("DELETE FROM registered_vehicles")
        conn.commit()
        conn.close()

    def test_hardware_controller_initialization_fallback(self):
        hw = ArduinoHardwareController(port="COM9999", enabled=True)
        self.assertFalse(hw.is_connected)
        status_dict = hw.get_status_dict()
        self.assertTrue(status_dict["enabled"])
        self.assertFalse(status_dict["is_connected"])

    def test_hardware_signals_on_confirmed_access_allowed(self):
        gc = GateController(gate_open_duration_sec=0.1)
        mock_hw = MagicMock()
        gc.hardware_controller = mock_hw

        # Register ACTIVE vehicle
        add_vehicle("GJ01AB1234", "Jay Shah", "A-501", "Car", "ACTIVE")

        confirmed_allowed = {
            "plate_number": "GJ01AB1234",
            "ocr_confidence": 0.96,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        res = gc.process_confirmed_plate(confirmed_allowed, is_entry=True)
        self.assertEqual(res["access_decision"], "ACCESS ALLOWED")
        self.assertEqual(res["gate_status"], "OPEN")

        # Verify OPEN signal was sent to hardware
        mock_hw.send_open_signal.assert_called()

        # Wait for auto-close timer
        time.sleep(0.2)
        # Verify CLOSE signal was sent to hardware
        mock_hw.send_close_signal.assert_called()

    def test_hardware_signals_on_access_denied(self):
        gc = GateController()
        mock_hw = MagicMock()
        gc.hardware_controller = mock_hw

        unregistered_res = {
            "plate_number": "MH99ZZ9999",
            "ocr_confidence": 0.93,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        res = gc.process_confirmed_plate(unregistered_res, is_entry=True)
        self.assertEqual(res["access_decision"], "ACCESS DENIED")
        self.assertEqual(res["gate_status"], "CLOSED")

        # Verify DENIED signal sent to hardware and OPEN was NEVER called
        mock_hw.send_denied_signal.assert_called()
        mock_hw.send_open_signal.assert_not_called()

    def test_hardware_safety_guard_unconfirmed_plate(self):
        gc = GateController()
        mock_hw = MagicMock()
        gc.hardware_controller = mock_hw

        unconfirmed_single_frame = {
            "plate_number": "GJ01AB1234",
            "ocr_confidence": 0.98,
            "status": "SEARCHING"
        }

        res = gc.process_confirmed_plate(unconfirmed_single_frame, is_entry=True)
        self.assertEqual(res["gate_status"], "CLOSED")

        # Verify hardware OPEN signal was NEVER called on unconfirmed plate
        mock_hw.send_open_signal.assert_not_called()
        mock_hw.send_denied_signal.assert_called()


if __name__ == '__main__':
    unittest.main()
