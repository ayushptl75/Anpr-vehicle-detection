from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify, send_from_directory
from config import ENTRY_CAMERA_URL, EXIT_CAMERA_URL, MIN_OCR_CONFIDENCE, STORAGE_DIR
from database.database import (
    init_db, get_vehicles_inside_count, list_vehicles,
    search_vehicles, add_vehicle, edit_vehicle, deactivate_vehicle,
    get_access_logs, get_vehicle_by_id, get_day_summary, get_gate_events
)
from anpr.camera import CameraService
from gate.gate_controller import gate_controller

app = Flask(__name__)
app.secret_key = "smart_society_sec_key"

# Initialize DB tables on app startup
init_db()

# Initialize separate ENTRY and EXIT camera services
entry_camera = CameraService(camera_url=ENTRY_CAMERA_URL, name="Entry Camera", is_entry=True)
exit_camera = CameraService(camera_url=EXIT_CAMERA_URL, name="Exit Camera", is_entry=False)

entry_camera.start()
exit_camera.start()

@app.route('/')
def dashboard():
    today_str = datetime.now().strftime("%Y-%m-%d")
    inside_count = get_vehicles_inside_count()
    summary = get_day_summary(today_str)
    
    # Calculate denied attempts for today
    today_events = get_gate_events(date_str=today_str, limit=500)
    denied_attempts = len([e for e in today_events if e.get('access_status') == 'DENIED'])
    
    recent_events = get_gate_events(limit=10)
    
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        vehicles_inside=inside_count,
        todays_entries=summary['entries'],
        todays_exits=summary['exits'],
        denied_attempts=denied_attempts,
        recent_activity=recent_events
    )

@app.route('/video_feed/entry')
def video_feed_entry():
    return Response(
        entry_camera.generate_mjpeg_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/video_feed/exit')
def video_feed_exit():
    return Response(
        exit_camera.generate_mjpeg_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/storage/<path:filename>')
def serve_storage(filename):
    return send_from_directory(STORAGE_DIR, filename)

@app.route('/api/gate-status', methods=['GET'])
def get_gate_status():
    return jsonify({
        "vehicles_inside": get_vehicles_inside_count(),
        "entry_gate_status": gate_controller.entry_gate_status,
        "exit_gate_status": gate_controller.exit_gate_status,
        "last_entry": gate_controller.last_entry_decision,
        "last_exit": gate_controller.last_exit_decision
    })

@app.route('/live-entry')
def live_entry():
    return render_template('live_entry.html', active_page='entry', camera_url=ENTRY_CAMERA_URL)

@app.route('/live-exit')
def live_exit():
    return render_template('live_exit.html', active_page='exit', camera_url=EXIT_CAMERA_URL)

@app.route('/vehicles')
def vehicles():
    query = request.args.get('q', '').strip()
    if query:
        vehicles_list = search_vehicles(query)
    else:
        vehicles_list = list_vehicles()
    
    edit_id = request.args.get('edit', type=int)
    edit_item = get_vehicle_by_id(edit_id) if edit_id else None

    return render_template('vehicles.html', active_page='vehicles', vehicles=vehicles_list, search_query=query, edit_item=edit_item)

@app.route('/vehicles/add', methods=['POST'])
def add_vehicle_route():
    plate = request.form.get('plate_number', '')
    resident = request.form.get('resident_name', '')
    flat = request.form.get('flat_number', '')
    vtype = request.form.get('vehicle_type', 'Car')
    status = request.form.get('status', 'ACTIVE')

    if plate and resident and flat:
        res = add_vehicle(plate, resident, flat, vtype, status)
        if not res["success"]:
            flash(res["error"], "danger")
    return redirect(url_for('vehicles'))

@app.route('/vehicles/edit/<int:vehicle_id>', methods=['POST'])
def edit_vehicle_route(vehicle_id):
    resident = request.form.get('resident_name', '')
    flat = request.form.get('flat_number', '')
    vtype = request.form.get('vehicle_type', 'Car')
    status = request.form.get('status', 'ACTIVE')

    if resident and flat:
        edit_vehicle(vehicle_id, resident, flat, vtype, status)
    return redirect(url_for('vehicles'))

@app.route('/vehicles/deactivate/<int:vehicle_id>', methods=['POST'])
def deactivate_vehicle_route(vehicle_id):
    deactivate_vehicle(vehicle_id)
    return redirect(url_for('vehicles'))

@app.route('/records')
def records():
    date_filter = request.args.get('date', '').strip()
    events = get_gate_events(date_str=date_filter if date_filter else None, limit=100)
    return render_template('records.html', active_page='records', events=events, date_filter=date_filter)

from reports.report_service import report_service

@app.route('/reports')
def reports():
    filter_type = request.args.get('filter_type', 'today').strip()
    specific_date = request.args.get('specific_date', datetime.now().strftime("%Y-%m-%d")).strip()
    start_date = request.args.get('start_date', datetime.now().strftime("%Y-%m-%d")).strip()
    end_date = request.args.get('end_date', datetime.now().strftime("%Y-%m-%d")).strip()

    report_data = report_service.generate_report(filter_type, specific_date, start_date, end_date)

    return render_template(
        'reports.html',
        active_page='reports',
        filter_type=filter_type,
        specific_date=specific_date,
        start_date=start_date,
        end_date=end_date,
        report=report_data
    )

@app.route('/reports/export/csv')
def export_csv_route():
    filter_type = request.args.get('filter_type', 'today').strip()
    specific_date = request.args.get('specific_date', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    report_data = report_service.generate_report(filter_type, specific_date, start_date, end_date)
    csv_content = report_service.export_csv(report_data)

    filename = f"gate_report_{report_data['start_date']}_to_{report_data['end_date']}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/reports/export/excel')
def export_excel_route():
    filter_type = request.args.get('filter_type', 'today').strip()
    specific_date = request.args.get('specific_date', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    report_data = report_service.generate_report(filter_type, specific_date, start_date, end_date)
    excel_csv_content = report_service.export_excel(report_data)

    filename = f"gate_report_{report_data['start_date']}_to_{report_data['end_date']}.csv"
    return Response(
        excel_csv_content,
        mimetype="application/vnd.ms-excel",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/reports/export/pdf')
def export_pdf_route():
    filter_type = request.args.get('filter_type', 'today').strip()
    specific_date = request.args.get('specific_date', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    report_data = report_service.generate_report(filter_type, specific_date, start_date, end_date)
    pdf_html = report_service.export_pdf_html(report_data)

    return Response(pdf_html, mimetype="text/html")

@app.route('/settings')
def settings():
    return render_template(
        'settings.html',
        active_page='settings',
        entry_camera_url=ENTRY_CAMERA_URL,
        exit_camera_url=EXIT_CAMERA_URL,
        min_ocr_confidence=MIN_OCR_CONFIDENCE
    )

if __name__ == '__main__':
    print("==========================================================")
    print("  Smart Society Security Gate System (Port 5000) Starting  ")
    print(f"  ENTRY_CAMERA_URL: {ENTRY_CAMERA_URL}")
    print(f"  EXIT_CAMERA_URL:  {EXIT_CAMERA_URL}")
    print("==========================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
