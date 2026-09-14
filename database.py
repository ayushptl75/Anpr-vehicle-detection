import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table 1: Registered Vehicles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registered_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE NOT NULL,
            owner_name TEXT NOT NULL,
            vehicle_type TEXT DEFAULT 'Car',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table 2: Access Logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            exit_time TIMESTAMP,
            entry_image_path TEXT,
            exit_image_path TEXT,
            plate_image_path TEXT,
            status TEXT NOT NULL,
            gate_decision TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

# --- Registered Vehicle CRUD ---

def get_registered_vehicles():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM registered_vehicles ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def is_plate_registered(plate_number: str):
    clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "")
    conn = get_db_connection()
    # Check exact match or normalized match
    row = conn.execute(
        "SELECT * FROM registered_vehicles WHERE REPLACE(REPLACE(UPPER(plate_number), ' ', ''), '-', '') = ?",
        (clean_plate,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def add_registered_vehicle(plate_number: str, owner_name: str, vehicle_type: str = 'Car'):
    clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO registered_vehicles (plate_number, owner_name, vehicle_type) VALUES (?, ?, ?)",
            (clean_plate, owner_name.strip(), vehicle_type.strip())
        )
        conn.commit()
        vehicle_id = cursor.lastrowid
        conn.close()
        return {"success": True, "id": vehicle_id}
    except sqlite3.IntegrityError:
        conn.close()
        return {"success": False, "error": "Plate number is already registered"}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}

def delete_registered_vehicle(vehicle_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM registered_vehicles WHERE id = ?", (vehicle_id,))
    conn.commit()
    conn.close()
    return True

# --- Access Log CRUD & Gate Authorization ---

def log_entry_event(plate_number: str, entry_image_path: str, plate_image_path: str, is_authorized: bool):
    clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "")
    status = 'INSIDE' if is_authorized else 'DENIED'
    gate_decision = 'GRANTED' if is_authorized else 'DENIED'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO access_logs (plate_number, entry_time, entry_image_path, plate_image_path, status, gate_decision)
        VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
    ''', (clean_plate, entry_image_path, plate_image_path, status, gate_decision))
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()
    
    return {
        "log_id": log_id,
        "plate_number": clean_plate,
        "status": status,
        "gate_decision": gate_decision
    }

def log_exit_event(plate_number: str, exit_image_path: str):
    clean_plate = plate_number.strip().upper().replace(" ", "").replace("-", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find active record inside
    row = cursor.execute(
        "SELECT id FROM access_logs WHERE REPLACE(REPLACE(UPPER(plate_number), ' ', ''), '-', '') = ? AND status = 'INSIDE' ORDER BY id DESC LIMIT 1",
        (clean_plate,)
    ).fetchone()
    
    if row:
        log_id = row['id']
        cursor.execute('''
            UPDATE access_logs 
            SET exit_time = CURRENT_TIMESTAMP, exit_image_path = ?, status = 'COMPLETED'
            WHERE id = ?
        ''', (exit_image_path, log_id))
        conn.commit()
        conn.close()
        return {
            "success": True,
            "log_id": log_id,
            "plate_number": clean_plate,
            "gate_decision": "GRANTED"
        }
    else:
        # Unmatched exit or vehicle not marked inside
        cursor.execute('''
            INSERT INTO access_logs (plate_number, exit_time, exit_image_path, status, gate_decision)
            VALUES (?, CURRENT_TIMESTAMP, ?, 'COMPLETED', 'GRANTED')
        ''', (clean_plate, exit_image_path))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        return {
            "success": True,
            "log_id": log_id,
            "plate_number": clean_plate,
            "gate_decision": "GRANTED"
        }

def get_vehicles_inside_count():
    conn = get_db_connection()
    row = conn.execute("SELECT COUNT(*) as count FROM access_logs WHERE status = 'INSIDE'").fetchone()
    conn.close()
    return row['count'] if row else 0

def get_day_wise_logs(target_date: str = None):
    conn = get_db_connection()
    if not target_date:
        target_date = datetime.now().strftime('%Y-%m-%d')
    
    rows = conn.execute('''
        SELECT * FROM access_logs 
        WHERE DATE(entry_time) = DATE(?) OR DATE(exit_time) = DATE(?)
        ORDER BY id DESC
    ''', (target_date, target_date)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_access_logs(limit: int = 20):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM access_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
