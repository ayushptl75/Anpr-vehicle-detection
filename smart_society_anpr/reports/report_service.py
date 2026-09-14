import io
import csv
from datetime import datetime
from database.database import get_report_records

class ReportService:
    def __init__(self):
        pass

    def generate_report(self, filter_type: str = "today", specific_date: str = None, start_date: str = None, end_date: str = None):
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if filter_type == "today":
            s_date = today_str
            e_date = today_str
        elif filter_type == "specific":
            s_date = specific_date or today_str
            e_date = s_date
        elif filter_type == "range":
            s_date = start_date or today_str
            e_date = end_date or s_date
        else:
            s_date = today_str
            e_date = today_str

        return get_report_records(s_date, e_date)

    def export_csv(self, report_data: dict) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        # Summary Header
        writer.writerow(["SMART SOCIETY SECURITY GATE REPORT"])
        writer.writerow(["Period", f"{report_data['start_date']} to {report_data['end_date']}"])
        writer.writerow(["Total Entries", report_data['total_entries']])
        writer.writerow(["Total Exits", report_data['total_exits']])
        writer.writerow(["Vehicles Currently Inside", report_data['currently_inside']])
        writer.writerow(["Denied Attempts", report_data['denied_attempts']])
        writer.writerow([])

        # Table Header
        writer.writerow(["Plate Number", "Entry Date", "Entry Time", "Exit Date", "Exit Time", "Status"])

        # Table Rows
        for r in report_data.get("records", []):
            writer.writerow([
                r["plate_number"],
                r["entry_date"],
                r["entry_time"],
                r["exit_date"],
                r["exit_time"],
                r["status"]
            ])

        return output.getvalue()

    def export_excel(self, report_data: dict) -> str:
        # Returns Excel-compatible CSV format
        return self.export_csv(report_data)

    def export_pdf_html(self, report_data: dict) -> str:
        # Generates clean printable HTML representation for PDF printing
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Gate Access Report ({report_data['start_date']} to {report_data['end_date']})</title>
            <style>
                body {{ font-family: sans-serif; margin: 30px; color: #1e293b; }}
                h1 {{ color: #0f172a; margin-bottom: 5px; }}
                .meta {{ color: #64748b; font-size: 14px; margin-bottom: 20px; }}
                .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
                .stat-box {{ border: 1px solid #cbd5e1; padding: 15px; border-radius: 8px; flex: 1; text-align: center; }}
                .stat-val {{ font-size: 24px; font-weight: bold; color: #38bdf8; margin-top: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #cbd5e1; padding: 10px; text-align: left; font-size: 14px; }}
                th {{ background: #f1f5f9; }}
            </style>
        </head>
        <body onload="window.print()">
            <h1>🛡️ Smart Society Gate Access Report</h1>
            <div class="meta">Report Period: <strong>{report_data['start_date']} to {report_data['end_date']}</strong></div>
            
            <div class="stats">
                <div class="stat-box"><div>Total Entries</div><div class="stat-val">{report_data['total_entries']}</div></div>
                <div class="stat-box"><div>Total Exits</div><div class="stat-val">{report_data['total_exits']}</div></div>
                <div class="stat-box"><div>Currently Inside</div><div class="stat-val">{report_data['currently_inside']}</div></div>
                <div class="stat-box"><div>Denied Attempts</div><div class="stat-val">{report_data['denied_attempts']}</div></div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Plate Number</th>
                        <th>Entry Date</th>
                        <th>Entry Time</th>
                        <th>Exit Date</th>
                        <th>Exit Time</th>
                    </tr>
                </thead>
                <tbody>
        """
        for r in report_data.get("records", []):
            html += f"""
                    <tr>
                        <td><strong>{r['plate_number']}</strong></td>
                        <td>{r['entry_date']}</td>
                        <td>{r['entry_time']}</td>
                        <td>{r['exit_date']}</td>
                        <td>{r['exit_time']}</td>
                    </tr>
            """
        html += """
                </tbody>
            </table>
        </body>
        </html>
        """
        return html

report_service = ReportService()
