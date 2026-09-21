import os
import cv2
import time
from datetime import datetime
from config import ENTRY_STORAGE_DIR, EXIT_STORAGE_DIR, PLATES_STORAGE_DIR
from database.database import (
    normalize_plate, is_vehicle_inside, create_entry_log, create_or_update_exit_log
)
from gate.gate_controller import gate_controller

class ANPRProcessor:
    def __init__(self, cooldown_sec=30.0):
        self.cooldown_sec = cooldown_sec
        self.entry_cooldowns = {}
        self.exit_cooldowns = {}

    def is_in_entry_cooldown(self, plate_number: str) -> bool:
        clean_plate = normalize_plate(plate_number)
        now = time.time()
        if clean_plate in self.entry_cooldowns:
            if now - self.entry_cooldowns[clean_plate] < self.cooldown_sec:
                return True
        return False

    def is_in_exit_cooldown(self, plate_number: str) -> bool:
        clean_plate = normalize_plate(plate_number)
        now = time.time()
        if clean_plate in self.exit_cooldowns:
            if now - self.exit_cooldowns[clean_plate] < self.cooldown_sec:
                return True
        return False

    def process_entry_event(self, frame, plate_crop, temporal_result: dict, camera_id: str = "ENTRY_CAM_1"):
        """
        Executes complete Entry Gate Workflow:
        1. Verifies plate status is CONFIRMED.
        2. Prevents duplicate entry events (vehicle already INSIDE or in cooldown).
        3. Evaluates registration status (REGISTERED + ACTIVE -> ACCESS ALLOWED vs ACCESS DENIED).
        4. Saves full vehicle frame & plate crop images to storage.
        5. Logs ENTRY event in database access_logs.
        6. Increases vehicles inside count for REGISTERED vehicles.
        7. Opens software gate for REGISTERED vehicles.
        """
        if not temporal_result or temporal_result.get("status") != "CONFIRMED":
            return {
                "success": False,
                "reason": "Plate not confirmed by multi-frame recognition",
                "access_decision": "PENDING"
            }

        clean_plate = normalize_plate(temporal_result.get("plate_number", ""))
        if not clean_plate:
            return {"success": False, "reason": "Missing or invalid plate number"}

        # 1. Duplicate Prevention Check
        if is_vehicle_inside(clean_plate):
            return {
                "success": False,
                "reason": f"Vehicle {clean_plate} is already inside. Duplicate entry prevented.",
                "duplicate": True,
                "plate_number": clean_plate
            }

        if self.is_in_entry_cooldown(clean_plate):
            return {
                "success": False,
                "reason": f"Vehicle {clean_plate} in entry cooldown. Duplicate entry prevented.",
                "duplicate": True,
                "plate_number": clean_plate
            }

        # 2. Database Authorization Check
        auth_info = gate_controller.evaluate_access(clean_plate)
        is_allowed = auth_info["access_decision"] == "ACCESS ALLOWED"
        gate_decision = "GRANTED" if is_allowed else "DENIED"

        # 3. Image Persistence
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        entry_img_filename = f"entry_{timestamp_str}_{clean_plate}.jpg"
        plate_img_filename = f"plate_{timestamp_str}_{clean_plate}.jpg"

        full_entry_path = os.path.join(ENTRY_STORAGE_DIR, entry_img_filename)
        full_plate_path = os.path.join(PLATES_STORAGE_DIR, plate_img_filename)

        rel_entry_path = f"/storage/entry/{entry_img_filename}"
        rel_plate_path = f"/storage/plates/{plate_img_filename}"

        if frame is not None and frame.size > 0:
            cv2.imwrite(full_entry_path, frame)
        else:
            rel_entry_path = None

        if plate_crop is not None and plate_crop.size > 0:
            cv2.imwrite(full_plate_path, plate_crop)
        else:
            rel_plate_path = rel_entry_path

        # 4. Create Entry Access Log in Database
        ocr_conf = float(temporal_result.get("ocr_confidence", 0.0))
        log_res = create_entry_log(
            plate_number=clean_plate,
            entry_image_path=rel_entry_path,
            plate_image_path=rel_plate_path,
            gate_decision=gate_decision,
            camera_id=camera_id,
            ocr_confidence=ocr_conf
        )

        # 5. Software Gate Decision & Cooldown Update
        if is_allowed:
            gate_controller.trigger_entry_gate_opening()
        else:
            with gate_controller.lock:
                gate_controller.entry_gate_status = "CLOSED"

        # Always update cooldown for processed plate to prevent duplicate event spamming
        self.entry_cooldowns[clean_plate] = time.time()

        res_dict = {
            "success": True,
            "log_id": log_res["log_id"],
            "plate_number": clean_plate,
            "auth_status": auth_info["auth_status"],
            "access_decision": auth_info["access_decision"],
            "gate_decision": gate_decision,
            "gate_status": "OPEN" if is_allowed else "CLOSED",
            "resident_name": auth_info["resident_name"],
            "flat_number": auth_info["flat_number"],
            "entry_image_path": rel_entry_path,
            "plate_image_path": rel_plate_path,
            "ocr_confidence": ocr_conf,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        gate_controller.last_entry_decision = res_dict
        return res_dict

    def process_exit_event(self, frame, plate_crop, temporal_result: dict, camera_id: str = "EXIT_CAM_1"):
        """
        Executes complete Exit Gate Workflow:
        1. Verifies plate status is CONFIRMED.
        2. Prevents duplicate exit events (vehicle already exited or in exit cooldown).
        3. Evaluates registration status (REGISTERED + ACTIVE -> ACCESS ALLOWED vs ACCESS DENIED).
        4. Saves full exit vehicle frame & plate crop images to storage.
        5. Updates access_logs matching active entry (updates exit_time, exit_image_path, status='COMPLETED').
        6. Decreases vehicles inside count for REGISTERED vehicles.
        7. Opens exit software gate for REGISTERED vehicles.
        """
        if not temporal_result or temporal_result.get("status") != "CONFIRMED":
            return {
                "success": False,
                "reason": "Plate not confirmed by multi-frame recognition",
                "access_decision": "PENDING"
            }

        clean_plate = normalize_plate(temporal_result.get("plate_number", ""))
        if not clean_plate:
            return {"success": False, "reason": "Missing or invalid plate number"}

        # 1. Duplicate Exit Prevention Check
        if self.is_in_exit_cooldown(clean_plate):
            return {
                "success": False,
                "reason": f"Vehicle {clean_plate} in exit cooldown. Duplicate exit prevented.",
                "duplicate": True,
                "plate_number": clean_plate
            }

        # 2. Database Authorization Check
        auth_info = gate_controller.evaluate_access(clean_plate)
        is_allowed = auth_info["access_decision"] == "ACCESS ALLOWED"
        gate_decision = "GRANTED" if is_allowed else "DENIED"

        # If vehicle is NOT inside and access allowed, prevent duplicate exit decrementing if already completed
        if is_allowed and not is_vehicle_inside(clean_plate) and self.is_in_exit_cooldown(clean_plate):
            return {
                "success": False,
                "reason": f"Vehicle {clean_plate} is already outside. Duplicate exit count decrease prevented.",
                "duplicate": True,
                "plate_number": clean_plate
            }

        # 3. Image Persistence for Exit
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        exit_img_filename = f"exit_{timestamp_str}_{clean_plate}.jpg"
        plate_img_filename = f"plate_{timestamp_str}_{clean_plate}.jpg"

        full_exit_path = os.path.join(EXIT_STORAGE_DIR, exit_img_filename)
        full_plate_path = os.path.join(PLATES_STORAGE_DIR, plate_img_filename)

        rel_exit_path = f"/storage/exit/{exit_img_filename}"
        rel_plate_path = f"/storage/plates/{plate_img_filename}"

        if frame is not None and frame.size > 0:
            cv2.imwrite(full_exit_path, frame)
        else:
            rel_exit_path = None

        if plate_crop is not None and plate_crop.size > 0:
            cv2.imwrite(full_plate_path, plate_crop)
        else:
            rel_plate_path = rel_exit_path

        # 4. Update or Create Exit Access Log in Database
        ocr_conf = float(temporal_result.get("ocr_confidence", 0.0))
        log_res = create_or_update_exit_log(
            plate_number=clean_plate,
            exit_image_path=rel_exit_path,
            plate_image_path=rel_plate_path,
            gate_decision=gate_decision,
            camera_id=camera_id,
            ocr_confidence=ocr_conf
        )

        # 5. Software Gate Decision & Cooldown Update
        if is_allowed:
            gate_controller.trigger_exit_gate_opening()
        else:
            with gate_controller.lock:
                gate_controller.exit_gate_status = "CLOSED"

        # Always update cooldown for processed plate to prevent duplicate exit event spamming
        self.exit_cooldowns[clean_plate] = time.time()

        res_dict = {
            "success": True,
            "log_id": log_res["log_id"],
            "plate_number": clean_plate,
            "auth_status": auth_info["auth_status"],
            "access_decision": auth_info["access_decision"],
            "gate_decision": gate_decision,
            "gate_status": "OPEN" if is_allowed else "CLOSED",
            "resident_name": auth_info["resident_name"],
            "flat_number": auth_info["flat_number"],
            "exit_image_path": rel_exit_path,
            "plate_image_path": rel_plate_path,
            "ocr_confidence": ocr_conf,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        gate_controller.last_exit_decision = res_dict
        return res_dict
