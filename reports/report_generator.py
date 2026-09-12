import csv
import os
from pathlib import Path
from database.database import (
    get_connection,
    get_attendance_analytics,
    get_student_attendance,
    get_student_profile
)

class ReportGenerator:
    """
    Generates CSV and HTML/PDF formatted reports for EduPilot.
    """

    @staticmethod
    def export_attendance_csv(filepath: str, subject_id: int = None) -> bool:
        """
        Exports all attendance records to a CSV file.
        """
        conn = get_connection()
        c = conn.cursor()
        
        query = """
            SELECT 
                ats.class_date,
                s.code AS subject_code,
                s.name AS subject_name,
                st.roll_number,
                st.name AS student_name,
                ar.status,
                ar.marked_at
            FROM attendance_records ar
            JOIN attendance_sessions ats ON ats.id = ar.session_id
            JOIN subjects s ON s.id = ats.subject_id
            JOIN students st ON st.id = ar.student_id
        """
        params = []
        if subject_id:
            query += " WHERE s.id = ?"
            params.append(subject_id)

        query += " ORDER BY ats.class_date DESC, st.roll_number ASC"
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Class Date", "Subject Code", "Subject Name", "Roll Number", "Student Name", "Status", "Marked At"])
            writer.writerows(rows)
            
        return True

    @staticmethod
    def export_classroom_analytics_csv(filepath: str) -> bool:
        """
        Exports overall student attendance analytics and percentages to CSV.
        """
        rows = get_attendance_analytics()
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Roll Number", "Student Name", "Total Sessions", "Classes Present", "Attendance Percentage", "Status Flag"])
            for r in rows:
                roll, name, total, present, pct = r
                flag = "Eligible" if pct >= 75 else "ALERT: Low Attendance"
                writer.writerow([roll, name, total, present, f"{pct}%", flag])

        return True

    @staticmethod
    def export_attendance_html_report(filepath: str, title: str = "EduPilot Attendance Summary") -> bool:
        """
        Generates a printable HTML report document (convertible to PDF by browser/print).
        """
        rows = get_attendance_analytics()
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        table_rows_html = ""
        for r in rows:
            roll, name, total, present, pct = r
            badge_color = "#10B981" if pct >= 75 else "#EF4444"
            status_text = "Good" if pct >= 75 else "Low (<75%)"
            table_rows_html += f"""
            <tr>
                <td>{roll}</td>
                <td><strong>{name}</strong></td>
                <td>{total}</td>
                <td>{present}</td>
                <td><span style="color: {badge_color}; font-weight: bold;">{pct}%</span></td>
                <td><span style="background-color: {badge_color}22; color: {badge_color}; padding: 4px 8px; border-radius: 4px; font-weight: 600;">{status_text}</span></td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background-color: #f8fafc; color: #1e293b; }}
        .header {{ border-bottom: 3px solid #2563eb; padding-bottom: 15px; margin-bottom: 25px; }}
        .header h1 {{ color: #1e3a8a; margin: 0; font-size: 24px; }}
        .header p {{ color: #64748b; margin: 5px 0 0 0; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background-color: #1e293b; color: white; text-align: left; padding: 12px; font-size: 13px; text-transform: uppercase; }}
        td {{ padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
        tr:nth-child(even) {{ background-color: #f1f5f9; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 15px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>Velammal College of Engineering & Technology (VCET) — EduPilot System Report</p>
    </div>

    <table>
        <thead>
            <tr>
                <th>Roll Number</th>
                <th>Student Name</th>
                <th>Total Classes</th>
                <th>Classes Attended</th>
                <th>Attendance %</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {table_rows_html}
        </tbody>
    </table>

    <div class="footer">
        Generated automatically by EduPilot Local Assistant • Velammal College of Engineering and Technology
    </div>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        return True

    @staticmethod
    def export_student_transcript_html(user_id: int, filepath: str) -> bool:
        """
        Generates an individual student academic & attendance transcript HTML report.
        """
        profile = get_student_profile(user_id)
        if not profile:
            return False

        att_summary = get_student_attendance(user_id)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        rows_html = ""
        for code, name, total, present in att_summary:
            pct = round((present / total * 100), 1) if total > 0 else 100.0
            color = "#10B981" if pct >= 75 else "#EF4444"
            rows_html += f"""
            <tr>
                <td><strong>{code}</strong></td>
                <td>{name}</td>
                <td>{total}</td>
                <td>{present}</td>
                <td><span style="color: {color}; font-weight: bold;">{pct}%</span></td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Student Academic Transcript - {profile[3]}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background-color: #ffffff; color: #0f172a; }}
        .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 25px; }}
        h1 {{ color: #1e3a8a; margin: 0 0 10px 0; font-size: 24px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th {{ background-color: #0f172a; color: white; text-align: left; padding: 10px; font-size: 12px; }}
        td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Student Performance Record</h1>
        <div class="grid">
            <div><strong>Name:</strong> {profile[3]}</div>
            <div><strong>Roll Number:</strong> {profile[2]}</div>
            <div><strong>Department:</strong> {profile[4]}</div>
            <div><strong>Year & Section:</strong> Year {profile[5]} - Section {profile[6]}</div>
        </div>
    </div>

    <h3>Subject Attendance & Progress</h3>
    <table>
        <thead>
            <tr>
                <th>Subject Code</th>
                <th>Subject Name</th>
                <th>Total Sessions</th>
                <th>Present</th>
                <th>Attendance %</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        return True

report_generator = ReportGenerator()
