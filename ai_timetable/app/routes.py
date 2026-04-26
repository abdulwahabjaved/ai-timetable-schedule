"""
routes.py — Flask routes for the AI Timetable System
FIXED VERSION: All 5 bugs resolved
  - Bug A: Double DB clear removed (route owns clearing, parser skips it)
  - Bug B: parse_pdf_to_db called with skip_clear=True
  - Bug C: db.session.remove() removed from parser (was killing request session)
  - Bug D: NameError on `filename` fixed — captured as `original_filename` upfront
  - Bug E: db.session.expire_all() added before conflict detection
"""

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request
from werkzeug.utils import secure_filename
from app.models import db, Teacher, Room, Course, Section, TimeSlot, Assignment, Conflict
from app.conflict_detector import ConflictDetector
import os
import uuid

main = Blueprint('main', __name__)


# ── Internal helper: safe DB wipe ─────────────────────────────────────────────

def _clear_all_timetable_data():
    """
    Delete all timetable rows in correct FK order.
    Does NOT call db.session.remove() — the request session stays alive.
    This is the ONLY place clearing should happen during an upload request.
    """
    try:
        # Conflicts table has FKs to assignments — MUST delete first
        db.session.query(Conflict).delete(synchronize_session=False)
        # Assignments hold all foreign keys — delete next
        db.session.query(Assignment).delete(synchronize_session=False)
        # Independent tables next (order among these doesn't matter)
        db.session.query(TimeSlot).delete(synchronize_session=False)
        db.session.query(Section).delete(synchronize_session=False)
        db.session.query(Course).delete(synchronize_session=False)
        db.session.query(Room).delete(synchronize_session=False)
        db.session.query(Teacher).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# ── Home / Dashboard ──────────────────────────────────────────────────────────

@main.route('/')
def index():
    stats = {
        'teachers':    Teacher.query.count(),
        'rooms':       Room.query.count(),
        'courses':     Course.query.count(),
        'sections':    Section.query.count(),
        'assignments': Assignment.query.count(),
        'conflicts':   0,
    }

    if stats['assignments'] > 0:
        try:
            # BUG E FIX: expire identity map so detector sees fresh DB rows
            db.session.expire_all()
            detector = ConflictDetector()
            report = detector.run()
            stats['conflicts'] = len(report.conflicts)
        except Exception:
            stats['conflicts'] = 0

    return render_template('index.html', stats=stats)


# ── Load sample data (DEPRECATED) ────────────────────────────────────────────
# ❌ Removed: System is now 100% upload-driven (no sample data)

@main.route('/load-data')
def load_data():
    """
    Deprecated route. System now requires uploaded PDF/CSV files.
    Redirects user to upload page with a helpful message.
    """
    flash(
        '[INFO] System is now 100% upload-driven. '
        'Please upload a PDF or CSV timetable file to get started.',
        'info'
    )
    return redirect(url_for('main.upload'))


# ── Conflict Detector — HTML page ─────────────────────────────────────────────

@main.route('/conflicts')
def conflicts():
    if Assignment.query.count() == 0:
        flash('No timetable data loaded yet. Please upload a PDF or CSV file first.', 'warning')
        return redirect(url_for('main.upload'))

    db.session.expire_all()
    detector = ConflictDetector()
    report = detector.run()

    return render_template(
        'conflicts.html',
        report=report,
        conflicts=report.sorted_conflicts(),
        counts=report.counts(),
        total=len(report.conflicts),
        scan_time=f"{report.scan_time_ms:.1f}",
        total_assignments=report.total_assignments,
    )


# ── Conflict Detector — JSON API ──────────────────────────────────────────────

@main.route('/api/conflicts')
def api_conflicts():
    db.session.expire_all()
    detector = ConflictDetector()
    report = detector.run()
    return jsonify({
        'total_conflicts':   len(report.conflicts),
        'total_assignments': report.total_assignments,
        'counts':            report.counts(),
        'scan_time_ms':      round(report.scan_time_ms, 2),
        'conflicts':         report.as_json(),
    })


# ── Timetable grid view ───────────────────────────────────────────────────────

@main.route('/timetable')
def timetable():
    assignments = (
        db.session.query(Assignment)
        .join(Teacher).join(Room).join(Section).join(Course).join(TimeSlot)
        .all()
    )
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    return render_template('timetable.html', assignments=assignments, days=days)


# ── Teachers Management ───────────────────────────────────────────────────────

@main.route('/teachers')
def teachers():
    all_teachers = Teacher.query.all()
    return render_template('teachers.html', teachers=all_teachers)


# ── Rooms Management ──────────────────────────────────────────────────────────

@main.route('/rooms')
def rooms():
    all_rooms = Room.query.all()
    return render_template('rooms.html', rooms=all_rooms)


# ── Analytics ─────────────────────────────────────────────────────────────────

@main.route('/analytics')
def analytics():
    return render_template('analytics.html')


# ── Upload page (GET) ─────────────────────────────────────────────────────────

@main.route('/upload')
def upload():
    return render_template('upload.html')


# ── Upload file (POST) ────────────────────────────────────────────────────────

@main.route('/upload', methods=['POST'])
def upload_file():
    """
    Handle PDF and CSV timetable upload.

    Fixed bugs:
      D — capture original_filename FIRST, before any branching
      A — clear DB exactly once via _clear_all_timetable_data(), not inside parser
      B — pass skip_clear=True so parser does not wipe again
      C — parser no longer calls db.session.remove() (fixed in parser.py)
      E — db.session.expire_all() before conflict detector
    """

    # ── Validate file presence ────────────────────────────────────────────────
    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('main.upload'))

    file = request.files['file']

    if not file or file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('main.upload'))

    # BUG D FIX: capture filename immediately — used in flash message later
    original_filename = file.filename

    filename_lower = original_filename.lower()
    is_pdf = filename_lower.endswith('.pdf')
    is_csv = filename_lower.endswith('.csv')

    if not (is_pdf or is_csv):
        flash('Only PDF and CSV files are supported.', 'error')
        return redirect(url_for('main.upload'))

    # ── Save file to temp location ────────────────────────────────────────────
    upload_dir = 'uploads'
    os.makedirs(upload_dir, exist_ok=True)

    # Clean any old files from previous uploads
    for old_file in os.listdir(upload_dir):
        old_path = os.path.join(upload_dir, old_file)
        try:
            if os.path.isfile(old_path):
                os.remove(old_path)
        except OSError:
            pass

    unique_name = f"{uuid.uuid4().hex}_{secure_filename(original_filename)}"
    filepath = os.path.join(upload_dir, unique_name)

    try:
        file.save(filepath)
    except Exception as e:
        flash(f'Could not save uploaded file: {e}', 'error')
        return redirect(url_for('main.upload'))

    # ── Parse & store ─────────────────────────────────────────────────────────
    try:
        # BUG A FIX: clear ONCE here, in correct FK order, session stays alive
        print(f"\n[CLEAR] Clearing database...")
        before_clear = Assignment.query.count()
        _clear_all_timetable_data()
        after_clear = Assignment.query.count()
        print(f"[OK] Cleared: Assignments {before_clear} -> {after_clear}")

        if is_pdf:
            from app.parser import parse_pdf_to_db
            # BUG B FIX: skip_clear=True — DB already wiped above
            summary = parse_pdf_to_db(filepath, skip_clear=True)
            file_type = "PDF"
        else:
            from app.parser import parse_csv_to_db
            # BUG B FIX: skip_clear=True — DB already wiped above
            summary = parse_csv_to_db(filepath, skip_clear=True)
            file_type = "CSV"

        print(f"\n[STATS] Parse Summary:")
        print(f"  Teachers: {summary['teachers']}")
        print(f"  Rooms: {summary['rooms']}")
        print(f"  Courses: {summary['courses']}")
        print(f"  Sections: {summary['sections']}")
        print(f"  Assignments: {summary['assignments']}")

        # BUG E FIX: discard identity-map cache before running conflict detector
        db.session.expire_all()

        try:
            detector = ConflictDetector()
            report = detector.run()
            conflicts_found = len(report.conflicts)
        except Exception:
            conflicts_found = 0

        # Surface parse warnings to user (show first 5 only)
        if summary.get('errors'):
            for err in summary['errors'][:5]:
                flash(f'[WARNING] {err}', 'warning')
            if len(summary['errors']) > 5:
                flash(f'... and {len(summary["errors"]) - 5} more errors.', 'warning')

        # BUG D FIX: original_filename is defined — no NameError
        flash(
            f'[OK] Successfully parsed {file_type} "{original_filename}"! '
            f'Loaded {summary["assignments"]} assignments, '
            f'{summary["teachers"]} teachers, '
            f'{summary["rooms"]} rooms, '
            f'{summary["sections"]} sections. '
            f'Conflicts detected: {conflicts_found}',
            'success'
        )

    except Exception as e:
        db.session.rollback()
        flash(f'Error parsing file: {e}', 'error')
        return redirect(url_for('main.upload'))

    finally:
        # Always remove the temp file, even on exception
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass

    return redirect(url_for('main.index'))


# ── Export ────────────────────────────────────────────────────────────────────

@main.route('/export')
def export_page():
    return render_template('export.html')


# ── DEBUG: inject conflicting test assignments ────────────────────────────────

@main.route('/debug/test-conflicts')
def test_conflicts():
    """
    Wipe assignments and create two overlapping slots for the same teacher
    so the conflict detector has something real to find.
    """
    db.session.query(Assignment).delete(synchronize_session=False)
    db.session.commit()

    teacher = Teacher.query.first()
    if not teacher:
        teacher = Teacher(name="Test Teacher", type="Regular")
        db.session.add(teacher)

    room1 = Room.query.filter_by(name="NAB CR224").first()
    if not room1:
        room1 = Room(name="NAB CR224", building="Dept of Software Engineering", room_type="Classroom")
        db.session.add(room1)

    room2 = Room.query.filter_by(name="NAB L-03").first()
    if not room2:
        room2 = Room(name="NAB L-03", building="Dept of Software Engineering", room_type="Lab")
        db.session.add(room2)

    course1 = Course.query.filter_by(code="CMPC-5201").first()
    if not course1:
        course1 = Course(code="CMPC-5201", name="Programming Fundamentals")
        db.session.add(course1)

    course2 = Course.query.filter_by(code="CMPC-5202").first()
    if not course2:
        course2 = Course(code="CMPC-5202", name="OOP")
        db.session.add(course2)

    section1 = Section.query.filter_by(program="BS", batch="2026-2030", semester=1).first()
    if not section1:
        section1 = Section(program="BS", batch="2026-2030", semester=1,
                           section_type="Regular", section_number=1)
        db.session.add(section1)

    ts_conflict = TimeSlot(day="Monday", start_time="09:30", end_time="11:00")
    db.session.add(ts_conflict)
    db.session.flush()

    a1 = Assignment(course=course1, teacher=teacher, room=room1,
                    section=section1, timeslot=ts_conflict, source='test')
    a2 = Assignment(course=course2, teacher=teacher, room=room2,
                    section=section1, timeslot=ts_conflict, source='test')
    db.session.add_all([a1, a2])
    db.session.commit()

    flash('[OK] Test data created with overlapping assignments. Visit /conflicts to verify.', 'info')
    return redirect(url_for('main.index'))