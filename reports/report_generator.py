import csv
import os
import tempfile
from html import escape
from pathlib import Path
from database.database import (
    get_connection,
    get_attendance_analytics,
    get_student_attendance,
    get_student_profile,
    get_student_academic_records,
)

class ReportGenerator:
    """
    Generates CSV and HTML/PDF formatted reports for EduPilot.
    """

    @staticmethod
    def _excel_workbook_type():
        try:
            from openpyxl import Workbook
        except ImportError as error:
            raise RuntimeError("Excel export needs openpyxl. Install the project dependencies from requirements.txt and try again.") from error
        return Workbook

    @staticmethod
    def export_attendance_csv(filepath: str, subject_id: int = None, start_date: str = None,
                              end_date: str = None, section: str = None) -> bool:
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
        conditions, params = [], []
        if subject_id:
            conditions.append("s.id = ?")
            params.append(subject_id)
        if start_date:
            conditions.append("ats.class_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ats.class_date <= ?")
            params.append(end_date)
        if section:
            conditions.append("ats.section = ?")
            params.append(section)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

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
    def export_attendance_xlsx(filepath: str, subject_id: int = None, start_date: str = None,
                               end_date: str = None, section: str = None) -> bool:
        Workbook = ReportGenerator._excel_workbook_type()
        conn = get_connection()
        query = """SELECT ats.class_date, s.code, s.name, st.roll_number, st.name, ar.status, ar.marked_at
            FROM attendance_records ar JOIN attendance_sessions ats ON ats.id = ar.session_id
            JOIN subjects s ON s.id = ats.subject_id JOIN students st ON st.id = ar.student_id"""
        conditions, params = [], []
        if subject_id:
            conditions.append("s.id = ?")
            params.append(subject_id)
        if start_date:
            conditions.append("ats.class_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ats.class_date <= ?")
            params.append(end_date)
        if section:
            conditions.append("ats.section = ?")
            params.append(section)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        rows = conn.execute(query + " ORDER BY ats.class_date DESC, st.roll_number", params).fetchall()
        conn.close()
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Attendance"
        sheet.append(["Class Date", "Subject Code", "Subject Name", "Roll Number", "Student Name", "Status", "Marked At"])
        for row in rows:
            sheet.append([ReportGenerator._excel_safe(value) for value in row])
        ReportGenerator._format_sheet(sheet)
        workbook.save(filepath)
        return True

    @staticmethod
    def export_attendance_pdf_report(filepath: str, title: str = "EduPilot Attendance Summary",
                                     start_date: str = None, end_date: str = None,
                                     subject_id: int = None, section: str = None) -> bool:
        from PySide6.QtGui import QTextDocument
        from PySide6.QtPrintSupport import QPrinter
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir=os.path.dirname(os.path.abspath(filepath))) as temporary:
            temporary_path = temporary.name
        try:
            ReportGenerator.export_attendance_html_report(temporary_path, title, start_date, end_date,
                                                          subject_id, section)
            document = QTextDocument()
            with open(temporary_path, "r", encoding="utf-8") as source:
                document.setHtml(source.read())
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(filepath)
            document.print_(printer)
            return os.path.isfile(filepath) and os.path.getsize(filepath) > 0
        finally:
            try:
                os.remove(temporary_path)
            except OSError:
                pass

    @staticmethod
    def export_student_transcript_xlsx(user_id: int, filepath: str) -> bool:
        Workbook = ReportGenerator._excel_workbook_type()
        profile = get_student_profile(user_id)
        if not profile:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        workbook = Workbook()
        attendance = workbook.active
        attendance.title = "Attendance"
        attendance.append(["Subject Code", "Subject Name", "Sessions", "Present", "Attendance %"])
        for code, name, total, present in get_student_attendance(user_id):
            percent = round(present / total * 100, 1) if total else None
            attendance.append([ReportGenerator._excel_safe(code), ReportGenerator._excel_safe(name), total, present, percent])
        academics = workbook.create_sheet("Academic Marks")
        academics.append(["Subject Code", "Subject Name", "Internal /100", "Assignment /100", "Lab /100", "Total /300"])
        for row in get_student_academic_records(user_id):
            academics.append([ReportGenerator._excel_safe(value) if isinstance(value, str) else value for value in row])
        profile_sheet = workbook.create_sheet("Student")
        profile_sheet.append(["Name", "Roll Number", "Department", "Year", "Section"])
        profile_sheet.append([ReportGenerator._excel_safe(profile[3]), ReportGenerator._excel_safe(profile[2]),
                              ReportGenerator._excel_safe(profile[4]), profile[5], ReportGenerator._excel_safe(profile[6])])
        for sheet in workbook.worksheets:
            ReportGenerator._format_sheet(sheet)
        workbook.save(filepath)
        return True

    @staticmethod
    def _excel_safe(value):
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    @staticmethod
    def _format_sheet(sheet):
        from openpyxl.styles import Font, PatternFill
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="354E60")
        for column in sheet.columns:
            width = min(48, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
            sheet.column_dimensions[column[0].column_letter].width = width

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
                flag = "No attendance" if total == 0 else ("Eligible" if pct >= 75 else "ALERT: Low Attendance")
                writer.writerow([roll, name, total, present, f"{pct}%" if total else "", flag])

        return True

    @staticmethod
    def export_attendance_html_report(filepath: str, title: str = "EduPilot Attendance Summary",
                                      start_date: str = None, end_date: str = None,
                                      subject_id: int = None, section: str = None) -> bool:
        """
        Generates a printable HTML report document (convertible to PDF by browser/print).
        """
        rows = get_attendance_analytics(start_date, end_date, subject_id, section)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        if start_date and end_date and start_date == end_date:
            period_description = f"Date: {start_date}"
        elif start_date or end_date:
            period_description = f"Period: {start_date or 'Beginning'} – {end_date or 'Today'}"
        else:
            period_description = "Period: All available dates"
        if section:
            period_description += f" · Section {section}"

        table_rows_html = ""
        for r in rows:
            roll, name, total, present, pct = r
            badge_color = "#48677D" if total and pct >= 75 else "#7A6B52"
            status_text = "No sessions" if not total else ("Good" if pct >= 75 else "Low (<75%)")
            table_rows_html += f"""
            <tr>
                <td>{escape(str(roll))}</td>
                <td><strong>{escape(str(name))}</strong></td>
                <td>{total}</td>
                <td>{present}</td>
                <td><span style="color: {badge_color}; font-weight: bold;">{f'{pct}%' if total else '—'}</span></td>
                <td><span style="background-color: {badge_color}22; color: {badge_color}; padding: 4px 8px; border-radius: 4px; font-weight: 600;">{status_text}</span></td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{escape(str(title))}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background-color: #FFFFFF; color: #26323B; }}
        .header {{ border-bottom: 3px solid #48677D; padding-bottom: 15px; margin-bottom: 25px; }}
        .header h1 {{ color: #263746; margin: 0; font-size: 24px; }}
        .header p {{ color: #687782; margin: 5px 0 0 0; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background-color: #26323B; color: white; text-align: left; padding: 12px; font-size: 13px; text-transform: uppercase; }}
        td {{ padding: 12px; border-bottom: 1px solid #DCE2E7; font-size: 14px; }}
        tr:nth-child(even) {{ background-color: #F4F6F8; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #687782; text-align: center; border-top: 1px solid #DCE2E7; padding-top: 15px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{escape(str(title))}</h1>
        <p>Velammal College of Engineering &amp; Technology (VCET) — EduPilot System Report</p>
        <p>{escape(period_description)}</p>
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
        academic_rows = get_student_academic_records(user_id)
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        rows_html = ""
        for code, name, total, present in att_summary:
            pct = round((present / total * 100), 1) if total > 0 else None
            color = "#48677D" if pct is not None and pct >= 75 else "#7A6B52"
            rows_html += f"""
            <tr>
                <td><strong>{escape(str(code))}</strong></td>
                <td>{escape(str(name))}</td>
                <td>{total}</td>
                <td>{present}</td>
                <td><span style="color: {color}; font-weight: bold;">{f'{pct}%' if pct is not None else '—'}</span></td>
            </tr>
            """

        academic_html = "".join(
            f"<tr><td>{escape(str(code))}</td><td>{escape(str(name))}</td>"
            f"<td>{internal:g}</td><td>{assignment:g}</td><td>{lab:g}</td><td>{total:g}/300</td></tr>"
            for code, name, internal, assignment, lab, total in academic_rows
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Student Academic Transcript - {escape(str(profile[3]))}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background-color: #ffffff; color: #26323B; }}
        .card {{ background: #FFFFFF; border: 1px solid #DCE2E7; border-radius: 10px; padding: 20px; margin-bottom: 25px; }}
        h1 {{ color: #263746; margin: 0 0 10px 0; font-size: 24px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th {{ background-color: #26323B; color: white; text-align: left; padding: 10px; font-size: 12px; }}
        td {{ padding: 10px; border-bottom: 1px solid #DCE2E7; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Student Performance Record</h1>
        <div class="grid">
            <div><strong>Name:</strong> {escape(str(profile[3]))}</div>
            <div><strong>Roll Number:</strong> {escape(str(profile[2]))}</div>
            <div><strong>Department:</strong> {escape(str(profile[4]))}</div>
            <div><strong>Year & Section:</strong> Year {profile[5]} - Section {profile[6]}</div>
        </div>
    </div>

    <h3>Published Academic Marks</h3>
    <table><thead><tr><th>Subject</th><th>Course</th><th>Internal /100</th><th>Assignment /100</th><th>Lab /100</th><th>Total</th></tr></thead>
    <tbody>{academic_html or '<tr><td colspan="6">No academic marks published</td></tr>'}</tbody></table>

    <h3>Subject Attendance</h3>
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
