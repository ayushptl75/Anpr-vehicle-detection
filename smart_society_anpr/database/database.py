import sqlite3
import os
import re
from datetime import datetime
from config import DATABASE_PATH

def normalize_plate(plate_number: str) -> str:
    """Normalizes license plate numbers: converts to uppercase, removes spaces and non-alphanumeric characters."""
    if not plate_number:
        return ""
    return re.sub(r'[^A-Z0-9]', '', plate_number.upper())

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # If legacy table exists with owner_name column, recreate with Phase 2 schema
    table_info = cursor.execute("PRAGMA table_info(registered_vehicles)").fetchall()
    cols = [c['name'] for c in table_info]
    if 'owner_name' in cols:
        cursor.execute("DROP TABLE registered_vehicles")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registered_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE NOT NULL,
            resident_name TEXT NOT NULL,
            flat_number TEXT NOT NULL,
            vehicle_type TEXT DEFAULT 'Car',
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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
            gate_decision TEXT NOT NULL,
            camera_id TEXT DEFAULT 'ENTRY_CAM',
            ocr_confidence REAL DEFAULT 0.0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gate_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL,
            gate TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            vehicle_image_path TEXT,
            plate_image_path TEXT,
            ocr_confidence REAL DEFAULT 0.0,
            access_status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration checks for access_logs
    log_cols = [c['name'] for c in cursor.execute("PRAGMA table_info(access_logs)").fetchall()]
    if 'camera_id' not in log_cols:
        cursor.execute("ALTER TABLE access_logs ADD COLUMN camera_id TEXT DEFAULT 'ENTRY_CAM'")
    if 'ocr_confidence' not in log_cols:
        cursor.execute("ALTER TABLE access_logs ADD COLUMN ocr_confidence REAL DEFAULT 0.0")

    conn.commit()
    conn.close()

# --- Registered Vehicle CRUD Operations ---

def add_vehicle(plate_number: str, resident_name: str, flat_number: str, vehicle_type: str = 'Car', status: str = 'ACTIVE'):
    clean_plate = normalize_plate(plate_number)
    if not clean_plate:
        return {"success": False, "error": "Invalid plate number"}
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO registered_vehicles (plate_number, resident_name, flat_number, vehicle_type, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (clean_plate, resident_name.strip(), flat_number.strip(), vehicle_type.strip(), status.strip().upper(), now, now))
        conn.commit()
        vid = cursor.lastrowid
        conn.close()
        return {"success": True, "id": vid, "plate_number": clean_plate}
    except sqlite3.IntegrityError:
        conn.close()
        return {"success": False, "error": f"Plate number '{clean_plate}' is already registered."}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}

def edit_vehicle(vehicle_id: int, resident_name: str, flat_number: str, vehicle_type: str, status: str):
    conn = get_db()
    try:
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            UPDATE registered_vehicles
            SET resident_name = ?, flat_number = ?, vehicle_type = ?, status = ?, updated_at = ?
            WHERE id = ?
        ''', (resident_name.strip(), flat_number.strip(), vehicle_type.strip(), status.strip().upper(), now, vehicle_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return {"success": updated}
    except Exception as e:
        conn.close()
        return {"success": False, "error": str(e)}

def deactivate_vehicle(vehicle_id: int):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE registered_vehicles
        SET status = 'INACTIVE', updated_at = ?
        WHERE id = ?
    ''', (now, vehicle_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return {"success": updated}

def search_vehicles(query: str):
    conn = get_db()
    clean_q = f"%{query.strip()}%"
    clean_plate_q = f"%{normalize_plate(query)}%"
    
    rows = conn.execute('''
        SELECT * FROM registered_vehicles
        WHERE plate_number LIKE ? 
           OR resident_name LIKE ? 
           OR flat_number LIKE ?
           OR vehicle_type LIKE ?
        ORDER BY id DESC
    ''', (clean_plate_q if query.strip() else clean_q, clean_q, clean_q, clean_q)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_vehicles():
    conn = get_db()
    rows = conn.execute("SELECT * FROM registered_vehicles ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_vehicle_by_id(vehicle_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM registered_vehicles WHERE id = ?", (vehicle_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_vehicle_by_plate(plate_number: str):
    clean_plate = normalize_plate(plate_number)
    conn = get_db()
    row = conn.execute("SELECT * FROM registered_vehicles WHERE plate_number = ?", (clean_plate,)).fetchone()
    conn.close()
    return dict(row) if row else None

def is_vehicle_inside(plate_number: str) -> bool:
    clean_plate = normalize_plate(plate_number)
    conn = get_db()
    row = conn.execute("SELECT id FROM access_logs WHERE plate_number = ? AND status = 'INSIDE'", (clean_plate,)).fetchone()
    conn.close()
    return row is not None

def create_entry_log(plate_number: str, entry_image_path: str, plate_image_path: str, gate_decision: str, camera_id: str = "ENTRY_CAM", ocr_confidence: float = 0.0):
    clean_plate = normalize_plate(plate_number)
    status = 'INSIDE' if gate_decision == 'GRANTED' else 'DENIED'
    
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO access_logs (plate_number, entry_time, entry_image_path, plate_image_path, status, gate_decision, camera_id, ocr_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (clean_plate, now, entry_image_path, plate_image_path, status, gate_decision, camera_id, ocr_confidence))
    conn.commit()
    log_id = cursor.lastrowid
    conn.close()

    # Log to gate_events
    access_status = 'ALLOWED' if gate_decision == 'GRANTED' else 'DENIED'
    create_gate_event(
        plate_number=clean_plate,
        event_type='ENTRY',
        gate='ENTRY_GATE',
        camera_id=camera_id,
        vehicle_image_path=entry_image_path,
        plate_image_path=plate_image_path,
        ocr_confidence=ocr_confidence,
        access_status=access_status
    )

    return {"log_id": log_id, "plate_number": clean_plate, "status": status, "gate_decision": gate_decision}

def create_or_update_exit_log(plate_number: str, exit_image_path: str, plate_image_path: str, gate_decision: str, camera_id: str = "EXIT_CAM", ocr_confidence: float = 0.0):
    clean_plate = normalize_plate(plate_number)
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check for active entry log with status 'INSIDE'
    row = cursor.execute(
        "SELECT id FROM access_logs WHERE plate_number = ? AND status = 'INSIDE' ORDER BY id DESC LIMIT 1",
        (clean_plate,)
    ).fetchone()

    if row and gate_decision == 'GRANTED':
        log_id = row['id']
        cursor.execute('''
            UPDATE access_logs
            SET exit_time = ?, exit_image_path = ?, status = 'COMPLETED', gate_decision = ?
            WHERE id = ?
        ''', (now, exit_image_path, gate_decision, log_id))
        conn.commit()
        conn.close()
        res_status = "COMPLETED"
        updated_existing = True
    else:
        status = 'COMPLETED' if gate_decision == 'GRANTED' else 'DENIED'
        cursor.execute('''
            INSERT INTO access_logs (plate_number, exit_time, exit_image_path, plate_image_path, status, gate_decision, camera_id, ocr_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (clean_plate, now, exit_image_path, plate_image_path, status, gate_decision, camera_id, ocr_confidence))
        conn.commit()
        log_id = cursor.lastrowid
        conn.close()
        res_status = status
        updated_existing = False

    # Log to gate_events
    access_status = 'ALLOWED' if gate_decision == 'GRANTED' else 'DENIED'
    create_gate_event(
        plate_number=clean_plate,
        event_type='EXIT',
        gate='EXIT_GATE',
        camera_id=camera_id,
        vehicle_image_path=exit_image_path,
        plate_image_path=plate_image_path,
        ocr_confidence=ocr_confidence,
        access_status=access_status
    )

    return {"log_id": log_id, "updated_existing": updated_existing, "plate_number": clean_plate, "status": res_status, "gate_decision": gate_decision}

def get_vehicles_inside_count():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM access_logs WHERE status = 'INSIDE'").fetchone()
    conn.close()
    return row['cnt'] if row else 0

def get_vehicles_inside_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM access_logs WHERE status = 'INSIDE' ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_access_logs(limit=50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM access_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Phase 10: Gate Events Database Operations ---

def create_gate_event(
    plate_number: str,
    event_type: str,
    gate: str,
    camera_id: str,
    vehicle_image_path: str,
    plate_image_path: str,
    ocr_confidence: float = 0.0,
    access_status: str = "ALLOWED",
    event_date: str = None,
    event_time: str = None
):
    clean_plate = normalize_plate(plate_number)
    now_dt = datetime.now()
    if not event_date:
        event_date = now_dt.strftime("%Y-%m-%d")
    if not event_time:
        event_time = now_dt.strftime("%H:%M:%S")

    clean_event_type = event_type.strip().upper()
    clean_access_status = access_status.strip().upper()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO gate_events (
            plate_number, event_type, event_date, event_time, gate, camera_id,
            vehicle_image_path, plate_image_path, ocr_confidence, access_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        clean_plate, clean_event_type, event_date, event_time, gate, camera_id,
        vehicle_image_path, plate_image_path, float(ocr_confidence), clean_access_status
    ))
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()

    return {
        "id": event_id,
        "plate_number": clean_plate,
        "event_type": clean_event_type,
        "event_date": event_date,
        "event_time": event_time,
        "gate": gate,
        "camera_id": camera_id,
        "access_status": clean_access_status
    }

def get_gate_events(date_str: str = None, limit: int = 50, event_type: str = None, access_status: str = None):
    conn = get_db()
    query = "SELECT * FROM gate_events"
    conditions = []
    params = []

    if date_str:
        clean_date = date_str.strip()
        if re.match(r'^\d{2}-\d{2}-\d{4}$', clean_date):
            d, m, y = clean_date.split('-')
            norm_date = f"{y}-{m}-{d}"
            conditions.append("(event_date = ? OR event_date = ?)")
            params.extend([norm_date, clean_date])
        else:
            conditions.append("event_date = ?")
            params.append(clean_date)

    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type.strip().upper())

    if access_status:
        conditions.append("access_status = ?")
        params.append(access_status.strip().upper())

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_day_summary(date_str: str = None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    clean_date = date_str.strip()
    norm_date = clean_date
    if re.match(r'^\d{2}-\d{2}-\d{4}$', clean_date):
        d, m, y = clean_date.split('-')
        norm_date = f"{y}-{m}-{d}"

    conn = get_db()

    entries_row = conn.execute('''
        SELECT COUNT(*) as cnt FROM gate_events
        WHERE (event_date = ? OR event_date = ?)
          AND event_type = 'ENTRY'
          AND access_status = 'ALLOWED'
    ''', (norm_date, clean_date)).fetchone()
    entries = entries_row['cnt'] if entries_row else 0

    exits_row = conn.execute('''
        SELECT COUNT(*) as cnt FROM gate_events
        WHERE (event_date = ? OR event_date = ?)
          AND event_type = 'EXIT'
          AND access_status = 'ALLOWED'
    ''', (norm_date, clean_date)).fetchone()
    exits = exits_row['cnt'] if exits_row else 0

    conn.close()

    currently_inside = get_vehicles_inside_count()

    return {
        "date": date_str,
        "entries": entries,
        "exits": exits,
        "currently_inside": currently_inside
    }

def get_report_records(start_date: str = None, end_date: str = None):
    now_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = now_date
    if not end_date:
        end_date = start_date

    conn = get_db()
    
    entries_cnt = conn.execute('''
        SELECT COUNT(*) as cnt FROM gate_events
        WHERE event_date >= ? AND event_date <= ?
          AND event_type = 'ENTRY' AND access_status = 'ALLOWED'
    ''', (start_date, end_date)).fetchone()['cnt']

    exits_cnt = conn.execute('''
        SELECT COUNT(*) as cnt FROM gate_events
        WHERE event_date >= ? AND event_date <= ?
          AND event_type = 'EXIT' AND access_status = 'ALLOWED'
    ''', (start_date, end_date)).fetchone()['cnt']

    denied_cnt = conn.execute('''
        SELECT COUNT(*) as cnt FROM gate_events
        WHERE event_date >= ? AND event_date <= ?
          AND access_status = 'DENIED'
    ''', (start_date, end_date)).fetchone()['cnt']

    rows = conn.execute('''
        SELECT * FROM access_logs
        WHERE (DATE(entry_time) >= ? AND DATE(entry_time) <= ?)
           OR (exit_time IS NOT NULL AND DATE(exit_time) >= ? AND DATE(exit_time) <= ?)
        ORDER BY id DESC
    ''', (start_date, end_date, start_date, end_date)).fetchall()

    records = []
    for r in rows:
        entry_t = r['entry_time']
        exit_t = r['exit_time']

        entry_date = entry_t.split()[0] if entry_t and ' ' in entry_t else (entry_t or "N/A")
        entry_time = entry_t.split()[1] if entry_t and ' ' in entry_t else "N/A"

        exit_date = exit_t.split()[0] if exit_t and ' ' in exit_t else ("N/A" if not exit_t else exit_t)
        exit_time = exit_t.split()[1] if exit_t and ' ' in exit_t else ("---" if not exit_t else "N/A")

        records.append({
            "id": r['id'],
            "plate_number": r['plate_number'],
            "entry_date": entry_date,
            "entry_time": entry_time,
            "exit_date": exit_date,
            "exit_time": exit_time,
            "status": r['status'],
            "gate_decision": r['gate_decision']
        })

    conn.close()

    currently_inside = get_vehicles_inside_count()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_entries": entries_cnt,
        "total_exits": exits_cnt,
        "currently_inside": currently_inside,
        "denied_attempts": denied_cnt,
        "records": records
    }


