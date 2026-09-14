from flask import Flask, render_template, Response, jsonify, request
import os
from database import (
    init_db, get_registered_vehicles, add_registered_vehicle, 
    delete_registered_vehicle, get_vehicles_inside_count, 
    get_recent_access_logs, get_day_wise_logs
)
from services.gate_service import gate_service
from services.camera_service import camera_service

app = Flask(__name__)

# Initialize DB tables on startup
init_db()

# Seed default registered vehicle if database is clean
existing_vehicles = get_registered_vehicles()
if len(existing_vehicles) == 0:
    add_registered_vehicle("MH12DE1432", "John Doe", "Car")
    add_registered_vehicle("KA01AB1234", "Alice Smith", "SUV")
    add_registered_vehicle("DL08CA9999", "Bob Johnson", "Bike")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed/entry')
def video_feed_entry():
    return Response(
        camera_service.generate_mjpeg_stream(is_entry=True),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/video_feed/exit')
def video_feed_exit():
    return Response(
        camera_service.generate_mjpeg_stream(is_entry=False),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "vehicles_inside": get_vehicles_inside_count(),
        "entry_gate": gate_service.entry_gate_status,
        "exit_gate": gate_service.exit_gate_status,
        "last_entry": gate_service.last_entry_event,
        "last_exit": gate_service.last_exit_event,
        "recent_logs": get_recent_access_logs(10)
    })

@app.route('/api/scan/entry', methods=['POST'])
def scan_entry():
    frame = camera_service.get_entry_frame()
    result = camera_service.process_frame_for_scan(frame, is_entry=True)
    return jsonify(result)

@app.route('/api/scan/exit', methods=['POST'])
def scan_exit():
    frame = camera_service.get_exit_frame()
    result = camera_service.process_frame_for_scan(frame, is_entry=False)
    return jsonify(result)

@app.route('/api/registered', methods=['GET'])
def list_registered():
    return jsonify(get_registered_vehicles())

@app.route('/api/registered/add', methods=['POST'])
def add_registered():
    data = request.json or {}
    plate = data.get('plate_number', '')
    owner = data.get('owner_name', '')
    vtype = data.get('vehicle_type', 'Car')
    if not plate or not owner:
        return jsonify({"success": False, "error": "Plate number and owner name are required"}), 400
    res = add_registered_vehicle(plate, owner, vtype)
    return jsonify(res)

@app.route('/api/registered/delete/<int:vehicle_id>', methods=['DELETE'])
def delete_registered(vehicle_id):
    success = delete_registered_vehicle(vehicle_id)
    return jsonify({"success": success})

@app.route('/api/logs/today', methods=['GET'])
def get_today_logs():
    logs = get_day_wise_logs()
    return jsonify(logs)

if __name__ == '__main__':
    print("==================================================")
    print("   ANPR Desktop System Server Starting on :5000   ")
    print("==================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
