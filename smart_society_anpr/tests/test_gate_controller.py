import unittest
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import init_db, add_vehicle, get_db, edit_vehicle
from gate.gate_controller import GateController

class TestGateController(unittest.TestCase):

    def setUp(self):
        init_db()
        conn = get_db()
        conn.execute("DELETE FROM registered_vehicles")
        conn.commit()
        conn.close()

    def test_unconfirmed_plate_rejected(self):
        gc = GateController()
        
        # Single frame or SEARCHING status
        unconfirmed_res = {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.95,
            "status": "SEARCHING"
        }
        res = gc.process_confirmed_plate(unconfirmed_res, is_entry=True)
        self.assertFalse(res["authorized"])
        self.assertEqual(res["access_decision"], "PENDING")
        self.assertEqual(res["gate_status"], "CLOSED")
        self.assertEqual(gc.entry_gate_status, "CLOSED")

    def test_confirmed_registered_active_vehicle(self):
        gc = GateController()
        
        # Register vehicle as ACTIVE
        add_vehicle(
            plate_number="GJ05 AB 1234",
            resident_name="Rahul Patel",
            flat_number="A-101",
            vehicle_type="Car",
            status="ACTIVE"
        )

        confirmed_res = {
            "plate_number": "GJ05AB1234",
            "ocr_confidence": 0.96,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        res = gc.process_confirmed_plate(confirmed_res, is_entry=True)
        self.assertEqual(res["auth_status"], "REGISTERED")
        self.assertEqual(res["access_decision"], "ACCESS ALLOWED")
        self.assertEqual(res["gate_status"], "OPEN")
        self.assertEqual(res["resident_name"], "Rahul Patel")
        self.assertEqual(gc.entry_gate_status, "OPEN")

    def test_confirmed_unregistered_vehicle(self):
        gc = GateController()

        confirmed_unregistered = {
            "plate_number": "KA99ZZ0000",
            "ocr_confidence": 0.92,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        res = gc.process_confirmed_plate(confirmed_unregistered, is_entry=True)
        self.assertEqual(res["auth_status"], "NOT REGISTERED")
        self.assertEqual(res["access_decision"], "ACCESS DENIED")
        self.assertEqual(res["gate_status"], "CLOSED")
        self.assertEqual(gc.entry_gate_status, "CLOSED")

    def test_confirmed_inactive_registered_vehicle(self):
        gc = GateController()

        # Add vehicle then deactivate
        add_res = add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "INACTIVE")

        confirmed_inactive = {
            "plate_number": "MH12DE1432",
            "ocr_confidence": 0.95,
            "validation_status": "VALID_INDIAN_PLATE",
            "status": "CONFIRMED"
        }

        res = gc.process_confirmed_plate(confirmed_inactive, is_entry=True)
        self.assertEqual(res["auth_status"], "NOT REGISTERED")
        self.assertEqual(res["access_decision"], "ACCESS DENIED")
        self.assertEqual(res["gate_status"], "CLOSED")
        self.assertEqual(gc.entry_gate_status, "CLOSED")

    def test_simulated_gate_auto_close_timer(self):
        gc = GateController(gate_open_duration_sec=0.2)
        
        add_vehicle("KA01AB9999", "Alice Smith", "C-303", "Car", "ACTIVE")
        confirmed_res = {
            "plate_number": "KA01AB9999",
            "ocr_confidence": 0.95,
            "status": "CONFIRMED"
        }

        res = gc.process_confirmed_plate(confirmed_res, is_entry=True)
        self.assertEqual(gc.entry_gate_status, "OPEN")
        
        # Wait for auto-close duration
        time.sleep(0.3)
        self.assertEqual(gc.entry_gate_status, "CLOSED")

if __name__ == '__main__':
    unittest.main()
