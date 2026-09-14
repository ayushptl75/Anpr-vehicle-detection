import unittest
import os
import sys

# Ensure smart_society_anpr package is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import (
    init_db, normalize_plate, add_vehicle, edit_vehicle,
    deactivate_vehicle, search_vehicles, list_vehicles,
    get_vehicle_by_id, get_vehicle_by_plate, get_db
)

class TestRegisteredVehiclesDB(unittest.TestCase):

    def setUp(self):
        # Initialize fresh database schema
        init_db()
        # Clean test table entries before each test
        conn = get_db()
        conn.execute("DELETE FROM registered_vehicles")
        conn.commit()
        conn.close()

    def test_normalize_plate(self):
        self.assertEqual(normalize_plate("GJ05 AB 1234"), "GJ05AB1234")
        self.assertEqual(normalize_plate("mh-12-de-1432"), "MH12DE1432")
        self.assertEqual(normalize_plate(" ka  01  ab  9999 "), "KA01AB9999")

    def test_add_vehicle(self):
        res = add_vehicle(
            plate_number="GJ05 AB 1234",
            resident_name="Rahul Patel",
            flat_number="A-101",
            vehicle_type="Car",
            status="ACTIVE"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["plate_number"], "GJ05AB1234")

        v = get_vehicle_by_plate("GJ05AB1234")
        self.assertIsNotNone(v)
        self.assertEqual(v["resident_name"], "Rahul Patel")
        self.assertEqual(v["flat_number"], "A-101")
        self.assertEqual(v["vehicle_type"], "Car")
        self.assertEqual(v["status"], "ACTIVE")

    def test_duplicate_plate_rejection(self):
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        res = add_vehicle("GJ05 AB 1234", "Duplicate User", "B-202", "Bike", "ACTIVE")
        self.assertFalse(res["success"])
        self.assertIn("already registered", res["error"].lower())

    def test_edit_vehicle(self):
        add_res = add_vehicle("KA01AB1234", "Alice Smith", "C-303", "Car", "ACTIVE")
        vid = add_res["id"]

        edit_res = edit_vehicle(
            vehicle_id=vid,
            resident_name="Alice Smith-Updated",
            flat_number="C-304",
            vehicle_type="SUV",
            status="ACTIVE"
        )
        self.assertTrue(edit_res["success"])

        v = get_vehicle_by_id(vid)
        self.assertEqual(v["resident_name"], "Alice Smith-Updated")
        self.assertEqual(v["flat_number"], "C-304")
        self.assertEqual(v["vehicle_type"], "SUV")

    def test_deactivate_vehicle(self):
        add_res = add_vehicle("DL08CA9999", "Bob Johnson", "D-404", "Bike", "ACTIVE")
        vid = add_res["id"]

        deact_res = deactivate_vehicle(vid)
        self.assertTrue(deact_res["success"])

        v = get_vehicle_by_id(vid)
        self.assertEqual(v["status"], "INACTIVE")

    def test_search_vehicles(self):
        add_vehicle("GJ05AB1234", "Rahul Patel", "A-101", "Car", "ACTIVE")
        add_vehicle("MH12DE1432", "Vikram Shah", "B-202", "SUV", "ACTIVE")

        # Search by plate
        res1 = search_vehicles("GJ05")
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0]["resident_name"], "Rahul Patel")

        # Search by resident name
        res2 = search_vehicles("Vikram")
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]["plate_number"], "MH12DE1432")

        # Search by flat number
        res3 = search_vehicles("A-101")
        self.assertEqual(len(res3), 1)
        self.assertEqual(res3[0]["plate_number"], "GJ05AB1234")

if __name__ == '__main__':
    unittest.main()
