"""
parser.py — PDF Timetable Parser for SE Department
FIXED VERSION:
  - Bug C FIX: db.session.remove() removed from clear_database() entirely
  - Bug A FIX: parse_pdf_to_db() and parse_csv_to_db() accept skip_clear=True
               so the route can own the single clear and parser never double-wipes
  - load_sample_data() still calls clear_database() safely (non-request context)

How it works:
1. Opens each page of the PDF with pdfplumber
2. Extracts text blocks grouped by position
3. Uses regex patterns to identify rooms, teachers, courses, sections, time slots
4. Saves everything into the database via SQLAlchemy models
"""

import re
import pdfplumber
import pandas as pd
from app.models import db, Teacher, Room, Course, Section, TimeSlot, Assignment, Conflict

# ─── Known days in column order ──────────────────────────────────────────────
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# ─── Time pattern: matches "08:00 - 09:30" or "(08:00 - 09:30)" ─────────────
TIME_RE = re.compile(r'\(?\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*\)?')

# ─── Course code pattern: e.g. #CMPC-5201 or #SECC-302 ──────────────────────
CODE_RE = re.compile(r'#([A-Z]+-[\w-]+)')

# ─── Section pattern ─────────────────────────────────────────────────────────
SECTION_RE = re.compile(
    r'(BS|MS)\s+in?\s*Software\s+Engineering\s+'
    r'(Regular|Self\s+Support|Weekend[^(]*)\s*(\d)?\s*'
    r'\(\s*(\d{4}-\d{4})\s*\)\s+Semester#(\d+)',
    re.IGNORECASE
)

# ─── Known teacher names (from the PDF header) ───────────────────────────────
KNOWN_TEACHERS = {
    "Naveed Ahmad": "Regular",
    "Asad Nazar Awan": "Visiting",
    "Abid Rafique": "Regular",
    "Quasira Ramzan": "Regular",
    "Farhana Sharif": "Regular",
    "Dr. Muhammad Ramzan": "Regular",
    "Dr. Syed Ali Haider shah": "Regular",
    "Areeba Shahzad": "Visiting",
    "Muhammad Umar Nissar Malik": "Visiting",
    "Khuram Shahzad": "Visiting",
    "Zulfiqar Ali": "Visiting",
    "Saud Bin Tahir": "Regular",
    "Ehsan Zakaullah": "Visiting",
    "Muhammad Azeem": "Visiting",
    "Abdul Satar": "Visiting",
    "Asif ur Rehman": "Visiting",
    "Rahat khan": "Visiting",
    "Ameer Hamza": "Visiting",
    "Javed Iqbal": "Visiting",
    "Anoosha Maryem": "Visiting",
    "Dr. Muhammad Summair Raza": "Regular",
    "Afia Tariq": "Visiting",
    "Abu Sufyan": "Visiting",
    "Hussain Akram mohayyodin": "Visiting",
    "muhammad umer farooq": "Visiting",
    "Dr. Ahmad Mustafa": "Regular",
    "Dr. Afzal Badshah": "Regular",
    "Taimoor Ali Mehndi": "Visiting",
    "Usman Sagheer": "Visiting",
    "Sana Batool": "Visiting",
    "Khalil Shah": "Visiting",
    "Aftab Haider Naqvi": "Visiting",
    "Saima Aslam": "Visiting",
    "Kashaf Hassan": "Visiting",
    "Ms Hafiza Anila Sajid": "Visiting",
    "Hadia Abu Bakar": "Visiting",
    "Mehwish Samad": "Visiting",
    "Ms. Usma": "Visiting",
    "Iqra Mushtaq": "Visiting",
    "Umme Aeman": "Visiting",
    "Khadija Malik": "Visiting",
    "Saima Riaz": "Visiting",
    "Dr. Muhammad Manazir": "Regular",
    "Laiba Ghafoor": "Visiting",
    "Mr. Mudassar Iqbal": "Visiting",
    "Atia Bajwa": "Visiting",
    "Hasnain Abid": "Visiting",
    "Muhammad Umer Iqbal": "Regular",
    "Ayesha Mahmood": "Visiting",
    "Ahsan Abdullah Malik": "Visiting",
    "Okasha Sarwar": "Visiting",
    "Nazia Abbas": "Visiting",
    "Mavra Abbas": "Visiting",
    "Fatima Masood": "Visiting",
    "Areeba Zarnab": "Visiting",
    "Memoona Ashraf": "Visiting",
    "Kinza Hanif": "Visiting",
    "Muhammad Aamir Khan": "Visiting",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: get or create DB objects
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_teacher(name: str, teacher_type: str = 'Visiting') -> Teacher:
    name = name.strip()
    teacher = Teacher.query.filter_by(name=name).first()
    if not teacher:
        ttype = KNOWN_TEACHERS.get(name, teacher_type)
        teacher = Teacher(name=name, type=ttype)
        db.session.add(teacher)
        db.session.flush()
    return teacher


def get_or_create_room(name: str, building: str = '') -> Room:
    name = name.strip()
    room = Room.query.filter_by(name=name).first()
    if not room:
        rtype = 'Lab' if 'L-' in name or 'Lab' in name else 'Hall' if 'Hall' in name else 'Classroom'
        room = Room(name=name, building=building, room_type=rtype)
        db.session.add(room)
        db.session.flush()
    return room


def get_or_create_course(code: str, name: str) -> Course:
    code = code.strip()
    course = Course.query.filter_by(code=code).first()
    if not course:
        course = Course(code=code, name=name.strip())
        db.session.add(course)
        db.session.flush()
    return course


def get_or_create_section(program: str, batch: str, semester: int,
                           section_type: str, section_number: int) -> Section:
    section = Section.query.filter_by(
        program=program, batch=batch, semester=semester,
        section_type=section_type, section_number=section_number
    ).first()
    if not section:
        section = Section(
            program=program, batch=batch, semester=semester,
            section_type=section_type, section_number=section_number
        )
        db.session.add(section)
        db.session.flush()
    return section


def get_or_create_timeslot(day: str, start: str, end: str) -> TimeSlot:
    ts = TimeSlot.query.filter_by(day=day, start_time=start, end_time=end).first()
    if not ts:
        ts = TimeSlot(day=day, start_time=start, end_time=end)
        db.session.add(ts)
        db.session.flush()
    return ts


# ─────────────────────────────────────────────────────────────────────────────
# Database clearing
# ─────────────────────────────────────────────────────────────────────────────

def clear_database():
    """
    Wipe all timetable rows in correct FK order.

    BUG C FIX: db.session.remove() has been REMOVED.
    That call was destroying the scoped session for the entire Flask request,
    causing every subsequent DB query in the same request to return empty results
    — which made it look like the new file was never parsed.

    This function is safe to call from non-request contexts (e.g. load_sample_data,
    CLI scripts). During web uploads, _clear_all_timetable_data() in routes.py
    is called instead so the request session stays alive.
    """
    db.session.query(Conflict).delete(synchronize_session=False)
    db.session.query(Assignment).delete(synchronize_session=False)
    db.session.query(TimeSlot).delete(synchronize_session=False)
    db.session.query(Section).delete(synchronize_session=False)
    db.session.query(Course).delete(synchronize_session=False)
    db.session.query(Room).delete(synchronize_session=False)
    db.session.query(Teacher).delete(synchronize_session=False)
    db.session.commit()
    # ✅ REMOVED: db.session.remove() — was silently killing the request session


# ─────────────────────────────────────────────────────────────────────────────
# Teacher name cleaning — fixes regex over-capture bug
# ─────────────────────────────────────────────────────────────────────────────

# Pre-sort known teachers by name length (longest first) for greedy matching
_KNOWN_TEACHERS_SORTED = sorted(KNOWN_TEACHERS.keys(), key=len, reverse=True)


def _clean_teacher_name(raw_name: str) -> str:
    """
    Clean extracted teacher name by matching against KNOWN_TEACHERS.

    The teacher_time_re regex `([A-Z][^\\n(]+?)` sometimes captures prefix
    text from section/course info as part of the teacher name, e.g.:
        "Semester#8 Anoosha Maryem"  →  should be "Anoosha Maryem"
        "Regular 1 Mavra Abbas"     →  should be "Mavra Abbas"

    Strategy:
      1. Direct match against KNOWN_TEACHERS (fast path)
      2. Check if any known teacher name is a suffix of the raw text
      3. Check if any known teacher name appears anywhere in the raw text
      4. Fallback: strip common prefix patterns (Semester#N, batch info, etc.)
    """
    raw_name = raw_name.strip()

    # 1. Direct match — already clean
    if raw_name in KNOWN_TEACHERS:
        return raw_name

    # 2. Check if any known teacher name ends the raw string
    raw_lower = raw_name.lower()
    for known in _KNOWN_TEACHERS_SORTED:
        if raw_lower.endswith(known.lower()):
            # Return the known-case version
            return known

    # 3. Check if any known teacher name appears anywhere in the raw text
    for known in _KNOWN_TEACHERS_SORTED:
        if known.lower() in raw_lower:
            return known

    # 4. Fallback: strip common noise prefixes
    cleaned = re.sub(
        r'^.*?Semester\s*#\s*\d+\s*',  # "...Semester#8 "
        '', raw_name
    ).strip()
    if cleaned and cleaned != raw_name:
        return cleaned

    # Strip section-type prefixes like "Regular 1 ", "Self Support 2 "
    cleaned = re.sub(
        r'^(?:Regular|Self\s+Support|Weekend[^)]*)\s*\d*\s*',
        '', raw_name, flags=re.IGNORECASE
    ).strip()
    if cleaned:
        return cleaned

    return raw_name


# ─────────────────────────────────────────────────────────────────────────────
# Parse a single cell text block into structured data
# ─────────────────────────────────────────────────────────────────────────────

def parse_cell(cell_text: str) -> list:
    """
    A single cell can contain multiple class entries stacked.
    Each entry has: course name + code, section info, teacher, time.
    Returns a list of dicts with keys: course_name, course_code,
    section_raw, teacher_name, start_time, end_time
    """
    results = []
    if not cell_text or len(cell_text.strip()) < 10:
        return results

    teacher_time_re = re.compile(
        r'([A-Z][^\n(]+?)\s*\((\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\)'
    )

    matches = list(teacher_time_re.finditer(cell_text))
    if not matches:
        return results

    prev_end = 0
    for match in matches:
        block = cell_text[prev_end:match.end()]
        prev_end = match.end()

        code_match = CODE_RE.search(block)
        course_code = code_match.group(1) if code_match else 'UNKNOWN'

        course_name = 'Unknown Course'
        first_hash = block.find('#')
        if first_hash > 0:
            course_name = block[:first_hash].strip()
            course_name = re.sub(r'^Combined\s+Class\s*\(\d+\)\s*', '', course_name).strip()

        section_match = SECTION_RE.search(block)
        section_raw = section_match.group(0) if section_match else ''

        # FIX: Clean teacher name to remove prefix junk from regex over-capture
        raw_teacher = match.group(1).strip()
        teacher_name = _clean_teacher_name(raw_teacher)
        start_time = match.group(2)
        end_time = match.group(3)

        results.append({
            'course_name':  course_name,
            'course_code':  course_code,
            'section_raw':  section_raw,
            'teacher_name': teacher_name,
            'start_time':   start_time,
            'end_time':     end_time,
        })

    return results


def parse_section_raw(raw: str):
    """Turn raw section string into (program, batch, semester, type, number)."""
    m = SECTION_RE.search(raw)
    if not m:
        return None
    program  = m.group(1).strip().upper()
    stype_raw = m.group(2).strip()
    snum     = int(m.group(3)) if m.group(3) else 1
    batch    = m.group(4).strip()
    semester = int(m.group(5))

    if 'Weekend' in stype_raw:
        stype = 'Weekend Self Support'
    elif 'Self Support' in stype_raw:
        stype = 'Self Support'
    else:
        stype = 'Regular'

    return program, batch, semester, stype, snum


# ─────────────────────────────────────────────────────────────────────────────
# Main parser: reads PDF and saves to database
# ─────────────────────────────────────────────────────────────────────────────

def parse_pdf_to_db(pdf_path: str, skip_clear: bool = False) -> dict:
    """
    Main entry point for PDF timetables.
    Reads the PDF and saves all assignments to the database.

    BUG A+B FIX: skip_clear parameter added.
    When called from upload_file() in routes.py, pass skip_clear=True because
    the route already cleared the DB via _clear_all_timetable_data().
    This prevents the double-wipe that was causing data loss.

    Args:
        pdf_path:   Path to the PDF file on disk.
        skip_clear: If True, skip the DB wipe (route already did it).
                    If False (default / standalone use), wipe before parsing.
    """
    if not skip_clear:
        clear_database()

    summary = {
        'teachers': 0, 'rooms': 0, 'courses': 0,
        'sections': 0, 'assignments': 0, 'errors': []
    }

    # ✅ NO pre-seeding: Only create teachers/rooms found in the actual file
    # KNOWN_TEACHERS is used ONLY for type lookup (Regular vs Visiting)

    print(f"\n[FILE] Parsing PDF: {pdf_path}")
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"  -> Page {page_num}/{page_count}...")

            words = page.extract_words(
                x_tolerance=3, y_tolerance=3,
                keep_blank_chars=False, use_text_flow=False
            )
            if not words:
                print(f"    [!] No text extracted from page {page_num}")
                continue

            full_text = page.extract_text() or ''
            _parse_text_blocks(full_text, summary)

    print(f"[OK] PDF parsing complete")
    print(f"  Before commit: Assignments={summary['assignments']}")
    
    db.session.commit()

    summary['teachers']   = Teacher.query.count()
    summary['rooms']      = Room.query.count()
    summary['courses']    = Course.query.count()
    summary['sections']   = Section.query.count()
    summary['assignments'] = Assignment.query.count()

    print(f"[OK] After commit: Teachers={summary['teachers']}, Rooms={summary['rooms']}, "
          f"Courses={summary['courses']}, Sections={summary['sections']}, "
          f"Assignments={summary['assignments']}")

    return summary


def _parse_text_blocks(text: str, summary: dict):
    """Parse full page text into room-day-class entries."""
    lines = text.split('\n')
    current_room     = None
    current_building = ''
    current_day      = None

    # FIX: Room regex now captures full room names including numbers after hyphen
    # Matches: NAB CR-224, ARB L-10, MAB L-03, JHB CR-VCR, NAB Hall-2,
    #          Physics Hall, Pharmacy Hall, Education Hall
    room_re     = re.compile(
        r'\b((?:Physics|Pharmacy|Education)\s+Hall'
        r'|[A-Z]{2,4}\s+(?:CR-?[\w-]+|L-[\w]+|Hall-?[\w]*)'
        r')\b'
    )
    building_re = re.compile(r'(Department of \w[\w\s]+|College of \w[\w\s]+)', re.IGNORECASE)

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        bm = building_re.search(line)
        if bm:
            current_building = bm.group(1).strip()

        rm = room_re.search(line)
        if rm:
            room_name    = rm.group(1).strip()
            current_room = get_or_create_room(room_name, current_building)

        # FIX: Use word boundary check to detect day names properly
        # Only match standalone day names, not substrings
        for day in DAYS:
            if re.search(r'\b' + day + r'\b', line):
                current_day = day
                break

        time_m = TIME_RE.search(line)
        if time_m and current_room and current_day:
            start_t = time_m.group(1)
            end_t   = time_m.group(2)

            block_lines = [line]
            j = i - 1
            while j >= max(0, i - 6):
                prev = lines[j].strip()
                if room_re.search(prev) or any(d in prev for d in DAYS):
                    break
                block_lines.insert(0, prev)
                j -= 1

            block_text = ' '.join(block_lines)
            entries = parse_cell(block_text)

            for entry in entries:
                _save_entry(entry, current_room, current_day, summary)

        i += 1


def _save_entry(entry: dict, room: Room, day: str, summary: dict):
    """Save a single parsed class entry to the database."""
    try:
        course  = get_or_create_course(entry['course_code'], entry['course_name'])
        teacher = get_or_create_teacher(entry['teacher_name'])

        parsed = parse_section_raw(entry['section_raw'])
        if not parsed:
            return
        program, batch, semester, stype, snum = parsed
        section  = get_or_create_section(program, batch, semester, stype, snum)
        timeslot = get_or_create_timeslot(day, entry['start_time'], entry['end_time'])

        existing = Assignment.query.filter_by(
            course_id=course.id,
            teacher_id=teacher.id,
            room_id=room.id,
            section_id=section.id,
            timeslot_id=timeslot.id
        ).first()

        if not existing:
            assignment = Assignment(
                course=course, teacher=teacher, room=room,
                section=section, timeslot=timeslot, source='parsed'
            )
            db.session.add(assignment)
            db.session.flush()
            summary['assignments'] += 1

    except Exception as e:
        summary['errors'].append(f"Error saving entry {entry.get('course_code')}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# CSV parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_csv_to_db(csv_path: str, skip_clear: bool = False) -> dict:
    """
    Parse a CSV file and insert timetable rows into the database.

    BUG A+B FIX: skip_clear parameter added (same logic as parse_pdf_to_db).

    Expected CSV columns (case-insensitive):
      course_code, course_name, teacher, room, building,
      day, start, end, program, batch, semester, section_type, section_number

    Missing columns are allowed; rows with insufficient data are skipped.
    """
    summary = {
        'teachers': 0, 'rooms': 0, 'courses': 0,
        'sections': 0, 'assignments': 0, 'errors': []
    }

    if not skip_clear:
        clear_database()

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        summary['errors'].append(f"Failed to read CSV: {e}")
        return summary

    # Normalize column names: lowercase, strip, spaces → underscores
    # This handles both "course_code" and "Course Code" style headers
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    cols = {c: c for c in df.columns}

    def col(name):
        """Case-insensitive column lookup with alias support."""
        name_lower = name.lower().replace(' ', '_')
        if name_lower in cols:
            return cols[name_lower]
        # Aliases: start_time → start, end_time → end, and vice versa
        aliases = {
            'start': 'start_time',
            'start_time': 'start',
            'end': 'end_time',
            'end_time': 'end',
            'course_code': 'coursecode',
            'course_name': 'coursename',
        }
        alt = aliases.get(name_lower)
        if alt and alt in cols:
            return cols[alt]
        return None

    for _, row in df.iterrows():
        try:
            code         = str(row[col('course_code')]).strip()  if col('course_code')  else ''
            cname        = str(row[col('course_name')]).strip()  if col('course_name')  else ''
            teacher_name = str(row[col('teacher')]).strip()      if col('teacher')      else ''
            room_name    = str(row[col('room')]).strip()         if col('room')         else ''
            building     = str(row[col('building')]).strip()     if col('building')     else ''
            day          = str(row[col('day')]).strip()          if col('day')          else ''
            start        = str(row[col('start')]).strip()        if col('start')        else ''
            end          = str(row[col('end')]).strip()          if col('end')          else ''
            program      = str(row[col('program')]).strip()      if col('program')      else ''
            batch        = str(row[col('batch')]).strip()        if col('batch')        else ''
            stype        = str(row[col('section_type')]).strip() if col('section_type') else 'Regular'

            semester = None
            if col('semester') and not pd.isna(row[col('semester')]):
                try:
                    semester = int(row[col('semester')])
                except ValueError:
                    pass

            snum = 1
            if col('section_number') and not pd.isna(row[col('section_number')]):
                try:
                    snum = int(row[col('section_number')])
                except ValueError:
                    pass

            # Skip rows missing mandatory fields
            if not (code and teacher_name and room_name and day and start
                    and end and program and batch and semester):
                summary['errors'].append(
                    f"Skipping incomplete row: {code} / {teacher_name} / {room_name}"
                )
                continue

            course   = get_or_create_course(code, cname or code)
            teacher  = get_or_create_teacher(teacher_name)
            room     = get_or_create_room(room_name, building)
            section  = get_or_create_section(program, batch, semester, stype, snum)
            timeslot = get_or_create_timeslot(day, start, end)

            existing = Assignment.query.filter_by(
                course_id=course.id, teacher_id=teacher.id,
                room_id=room.id, section_id=section.id,
                timeslot_id=timeslot.id
            ).first()

            if not existing:
                db.session.add(Assignment(
                    course=course, teacher=teacher, room=room,
                    section=section, timeslot=timeslot, source='parsed'
                ))
                summary['assignments'] += 1

        except Exception as e:
            summary['errors'].append(f"Row error: {e}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        summary['errors'].append(f"DB commit failed: {e}")

    summary['teachers'] = Teacher.query.count()
    summary['rooms']    = Room.query.count()
    summary['courses']  = Course.query.count()
    summary['sections'] = Section.query.count()
    return summary


# ✅ PRODUCTION SYSTEM: No sample data — 100% upload-driven
# All timetable data comes from uploaded PDF/CSV files only.
# No demo data, no fallback logic, no hardcoded timetable.