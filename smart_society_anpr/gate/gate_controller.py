import time
import threading
from datetime import datetime
from database.database import get_vehicle_by_plate, normalize_plate

class GateController:
    def __init__(self, gate_open_duration_sec=5.0):
        self.entry_gate_status = "CLOSED"
        self.exit_gate_status = "CLOSED"
        self.gate_open_duration_sec = gate_open_duration_sec
        self.last_entry_decision = None
        self.last_exit_decision = None
        self.lock = threading.Lock()

    def evaluate_access(self, plate_number: str):
        """
        Queries registered_vehicles database.
        Returns authorization decision strictly based on ACTIVE registration status.
        """
        clean_plate = normalize_plate(plate_number)
        if not clean_plate:
            return {
                "auth_status": "NOT REGISTERED",
                "access_decision": "ACCESS DENIED",
                "resident_name": "N/A",
                "flat_number": "N/A"
            }

        vehicle = get_vehicle_by_plate(clean_plate)
        
        if vehicle and vehicle.get("status") == "ACTIVE":
            return {
                "auth_status": "REGISTERED",
                "access_decision": "ACCESS ALLOWED",
                "resident_name": vehicle.get("resident_name", "Resident"),
                "flat_number": vehicle.get("flat_number", "N/A")
            }
        else:
            return {
                "auth_status": "NOT REGISTERED",
                "access_decision": "ACCESS DENIED",
                "resident_name": "UNREGISTERED",
                "flat_number": "N/A"
            }

    def trigger_entry_gate_opening(self):
        """Opens entry software gate and starts auto-close timer thread."""
        with self.lock:
            self.entry_gate_status = "OPEN"

        def auto_close():
            time.sleep(self.gate_open_duration_sec)
            with self.lock:
                self.entry_gate_status = "CLOSED"

        threading.Thread(target=auto_close, daemon=True).start()

    def trigger_exit_gate_opening(self):
        """Opens exit software gate and starts auto-close timer thread."""
        with self.lock:
            self.exit_gate_status = "OPEN"

        def auto_close():
            time.sleep(self.gate_open_duration_sec)
            with self.lock:
                self.exit_gate_status = "CLOSED"

        threading.Thread(target=auto_close, daemon=True).start()

    def process_confirmed_plate(self, temporal_result: dict, is_entry: bool = True):
        """
        Processes plate for gate authorization decision.
        CRITICAL RULE: Only plates with temporal status == 'CONFIRMED' can reach access decision.
        Never use a single OCR frame for authorization.
        """
        if not temporal_result or temporal_result.get("status") != "CONFIRMED":
            return {
                "authorized": False,
                "reason": "Plate not yet CONFIRMED by multi-frame recognition",
                "access_decision": "PENDING",
                "gate_status": "CLOSED"
            }

        plate_number = temporal_result.get("plate_number", "")
        access_info = self.evaluate_access(plate_number)

        decision_result = {
            "plate_number": plate_number,
            "auth_status": access_info["auth_status"],
            "access_decision": access_info["access_decision"],
            "resident_name": access_info["resident_name"],
            "flat_number": access_info["flat_number"],
            "ocr_confidence": temporal_result.get("ocr_confidence", 0.0),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if is_entry:
            if access_info["access_decision"] == "ACCESS ALLOWED":
                self.trigger_entry_gate_opening()
                decision_result["gate_status"] = "OPEN"
            else:
                with self.lock:
                    self.entry_gate_status = "CLOSED"
                decision_result["gate_status"] = "CLOSED"
            self.last_entry_decision = decision_result
        else:
            if access_info["access_decision"] == "ACCESS ALLOWED":
                self.trigger_exit_gate_opening()
                decision_result["gate_status"] = "OPEN"
            else:
                with self.lock:
                    self.exit_gate_status = "CLOSED"
                decision_result["gate_status"] = "CLOSED"
            self.last_exit_decision = decision_result

        return decision_result


# Singleton Instance
gate_controller = GateController()
