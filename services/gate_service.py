import os
import cv2
from datetime import datetime
import threading
import time
from config import ENTRY_CAPTURES_DIR, EXIT_CAPTURES_DIR
from database import is_plate_registered, log_entry_event, log_exit_event

class GateService:
    def __init__(self):
        self.entry_gate_status = "CLOSED"
        self.exit_gate_status = "CLOSED"
        self.last_entry_event = None
        self.last_exit_event = None

    def trigger_entry_gate(self, duration_sec: int = 5):
        """Simulates Entry Gate Opening for duration_sec seconds."""
        self.entry_gate_status = "OPEN"
        def auto_close():
            time.sleep(duration_sec)
            self.entry_gate_status = "CLOSED"
        threading.Thread(target=auto_close, daemon=True).start()

    def trigger_exit_gate(self, duration_sec: int = 5):
        """Simulates Exit Gate Opening for duration_sec seconds."""
        self.exit_gate_status = "OPEN"
        def auto_close():
            time.sleep(duration_sec)
            self.exit_gate_status = "CLOSED"
        threading.Thread(target=auto_close, daemon=True).start()

    def process_entry_vehicle(self, plate_number: str, frame, plate_crop):
        """
        Handles full entry authorization workflow:
        1. Checks database registration status.
        2. Saves full vehicle frame & plate crop images to disk.
        3. Records access log with decision ('GRANTED' / 'DENIED').
        4. Triggers software gate simulation.
        """
        if not plate_number or len(plate_number) < 4:
            return {"success": False, "reason": "Invalid or missing plate number"}

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "")

        # Image Paths
        entry_frame_filename = f"entry_{timestamp_str}_{clean_plate}.jpg"
        plate_crop_filename = f"plate_{timestamp_str}_{clean_plate}.jpg"
        
        full_frame_path = os.path.join(ENTRY_CAPTURES_DIR, entry_frame_filename)
        plate_crop_path = os.path.join(ENTRY_CAPTURES_DIR, plate_crop_filename)
        
        rel_frame_path = f"/static/captures/entry/{entry_frame_filename}"
        rel_plate_path = f"/static/captures/entry/{plate_crop_filename}"

        if frame is not None and frame.size > 0:
            cv2.imwrite(full_frame_path, frame)
        
        if plate_crop is not None and plate_crop.size > 0:
            cv2.imwrite(plate_crop_path, plate_crop)
        else:
            rel_plate_path = rel_frame_path

        # 1. Registration Check
        registered_info = is_plate_registered(clean_plate)
        is_authorized = registered_info is not None

        # 2. Database Log Insertion
        log_res = log_entry_event(
            plate_number=clean_plate,
            entry_image_path=rel_frame_path,
            plate_image_path=rel_plate_path,
            is_authorized=is_authorized
        )

        # 3. Gate Simulation Decision
        if is_authorized:
            self.trigger_entry_gate()

        event_detail = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plate_number": clean_plate,
            "owner_name": registered_info["owner_name"] if is_authorized else "UNREGISTERED",
            "is_authorized": is_authorized,
            "gate_decision": "GRANTED" if is_authorized else "DENIED",
            "entry_image_path": rel_frame_path,
            "plate_image_path": rel_plate_path,
            "log_id": log_res["log_id"]
        }
        self.last_entry_event = event_detail
        return event_detail

    def process_exit_vehicle(self, plate_number: str, frame):
        """
        Handles exit authorization workflow:
        1. Saves exit frame.
        2. Logs exit event & matches active entry record.
        3. Opens software exit gate.
        """
        if not plate_number or len(plate_number) < 4:
            return {"success": False, "reason": "Invalid or missing plate number"}

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "")

        exit_frame_filename = f"exit_{timestamp_str}_{clean_plate}.jpg"
        full_frame_path = os.path.join(EXIT_CAPTURES_DIR, exit_frame_filename)
        rel_frame_path = f"/static/captures/exit/{exit_frame_filename}"

        if frame is not None and frame.size > 0:
            cv2.imwrite(full_frame_path, frame)

        # Log Exit Event in DB
        log_res = log_exit_event(
            plate_number=clean_plate,
            exit_image_path=rel_frame_path
        )

        # Trigger Exit Gate Simulation
        self.trigger_exit_gate()

        event_detail = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plate_number": clean_plate,
            "gate_decision": "GRANTED",
            "exit_image_path": rel_frame_path,
            "log_id": log_res["log_id"]
        }
        self.last_exit_event = event_detail
        return event_detail

# Global Singleton Instance
gate_service = GateService()
