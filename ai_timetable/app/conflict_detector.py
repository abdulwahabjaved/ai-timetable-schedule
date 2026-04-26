"""
conflict_detector.py — AI Conflict Detection Engine
====================================================
FIXED VERSION:
  - Bug E FIX: ConflictDetector.run() calls db.session.expire_all() before
    loading assignments so SQLAlchemy identity-map cache is never used.
    This guarantees the detector always reads fresh rows from the database,
    not stale objects left over from a previous request.

Scans the timetable database and finds ALL conflicts with severity ratings.

Conflict Types Detected:
  1. CRITICAL — Teacher Double-Booking    : Same teacher, same time, different rooms
  2. CRITICAL — Room Double-Booking       : Same room, same time, different sections
  3. HIGH     — Section Double-Booking    : Same section, same time, two subjects
  4. MEDIUM   — Teacher Overload          : Teacher has > N classes per day
  5. LOW      — Back-to-Back with Travel  : Teacher in different buildings, no gap
  6. LOW      — Long Section Day          : Section has > 3 slots in one day (student fatigue)

Usage:
    from app.conflict_detector import ConflictDetector
    detector = ConflictDetector()
    report = detector.run()
    print(report.summary())
"""

from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict
from typing import List, Optional
import pandas as pd
from app.models import Assignment, Teacher, Room, Section, TimeSlot, Course, db


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
SEVERITY_COLOR = {
    "CRITICAL": "#e74c3c",
    "HIGH":     "#e67e22",
    "MEDIUM":   "#f1c40f",
    "LOW":      "#3498db",
}
SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH":     "🟠",
    "MEDIUM":   "🟡",
    "LOW":      "🔵",
}


@dataclass
class Conflict:
    """Represents a single detected conflict."""
    conflict_type: str          # e.g. "Teacher Double-Booking"
    severity: str               # CRITICAL / HIGH / MEDIUM / LOW
    description: str            # human-readable message
    affected_ids: List[int]     # assignment IDs involved
    day: Optional[str] = None
    time_slot: Optional[str] = None
    entity_name: Optional[str] = None   # teacher/room/section name

    @property
    def severity_color(self) -> str:
        return SEVERITY_COLOR.get(self.severity, "#95a5a6")

    @property
    def severity_emoji(self) -> str:
        return SEVERITY_EMOJI.get(self.severity, "⚪")

    def to_dict(self) -> dict:
        return {
            "type":           self.conflict_type,
            "severity":       self.severity,
            "severity_color": self.severity_color,
            "severity_emoji": self.severity_emoji,
            "description":    self.description,
            "day":            self.day,
            "time_slot":      self.time_slot,
            "entity":         self.entity_name,
            "assignment_ids": self.affected_ids,
        }


@dataclass
class ConflictReport:
    """Full report returned after running the detector."""
    conflicts:         List[Conflict] = field(default_factory=list)
    total_assignments: int   = 0
    scan_time_ms:      float = 0.0

    def add(self, conflict: Conflict):
        self.conflicts.append(conflict)

    def sorted_conflicts(self) -> List[Conflict]:
        """Return conflicts sorted by severity (CRITICAL first)."""
        return sorted(self.conflicts, key=lambda c: SEVERITY_RANK.get(c.severity, 99))

    def by_severity(self) -> dict:
        groups = defaultdict(list)
        for c in self.conflicts:
            groups[c.severity].append(c)
        return dict(groups)

    def counts(self) -> dict:
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for c in self.conflicts:
            counts[c.severity] = counts.get(c.severity, 0) + 1
        return counts

    def summary(self) -> str:
        c = self.counts()
        total = len(self.conflicts)
        lines = [
            "=" * 55,
            "  AI TIMETABLE CONFLICT DETECTION REPORT",
            "=" * 55,
            f"  Total assignments scanned : {self.total_assignments}",
            f"  Total conflicts found     : {total}",
            f"  Scan time                 : {self.scan_time_ms:.1f} ms",
            "",
            f"  🔴 CRITICAL : {c['CRITICAL']}",
            f"  🟠 HIGH     : {c['HIGH']}",
            f"  🟡 MEDIUM   : {c['MEDIUM']}",
            f"  🔵 LOW      : {c['LOW']}",
            "=" * 55,
        ]
        for conflict in self.sorted_conflicts():
            lines.append(
                f"\n{conflict.severity_emoji} [{conflict.severity}] {conflict.conflict_type}"
                f"\n   {conflict.description}"
                f"\n   📅 {conflict.day or '—'}  ⏰ {conflict.time_slot or '—'}"
                f"\n   🏷  Entity: {conflict.entity_name or '—'}"
            )
        return "\n".join(lines)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.conflicts:
            return pd.DataFrame()
        return pd.DataFrame([c.to_dict() for c in self.sorted_conflicts()])

    def as_json(self) -> list:
        return [c.to_dict() for c in self.sorted_conflicts()]


# ─────────────────────────────────────────────────────────────────────────────
# Main Detector
# ─────────────────────────────────────────────────────────────────────────────

class ConflictDetector:
    """
    Loads all assignments from the DB and runs every conflict check.
    Designed to be called fresh each time (stateless between runs).
    """

    # Tunable thresholds
    MAX_CLASSES_PER_TEACHER_PER_DAY = 4
    MAX_CLASSES_PER_SECTION_PER_DAY = 4
    TRAVEL_TIME_MINUTES = 15

    def __init__(self):
        self.report = ConflictReport()
        self._assignments: list = []

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> ConflictReport:
        """Run all conflict checks and return the full report."""
        import time
        start = time.time()

        # BUG E FIX: discard any SQLAlchemy identity-map cache so we always
        # read live rows from the DB, not stale objects from a previous request.
        db.session.expire_all()

        self._load_assignments()
        self.report.total_assignments = len(self._assignments)

        self._check_teacher_double_booking()
        self._check_room_double_booking()
        self._check_section_double_booking()
        self._check_teacher_overload()
        self._check_back_to_back_travel()
        self._check_section_long_day()

        self.report.scan_time_ms = (time.time() - start) * 1000

        print(f"\n{'='*70}")
        print(f"[OK] SCAN COMPLETE")
        print(f"{'='*70}")
        print(f"Total conflicts found: {len(self.report.conflicts)}")
        counts = self.report.counts()
        print(f"  [!] CRITICAL: {counts['CRITICAL']}")
        print(f"  [*] HIGH:     {counts['HIGH']}")
        print(f"  [-] MEDIUM:   {counts['MEDIUM']}")
        print(f"  [ ] LOW:      {counts['LOW']}")
        print(f"Scan time: {self.report.scan_time_ms:.2f} ms")
        print(f"{'='*70}\n")

        return self.report

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_assignments(self):
        """Load all assignment rows from the database into flat dicts."""
        try:
            rows = (
                db.session.query(
                    Assignment.id,
                    Teacher.id.label("teacher_id"),
                    Teacher.name.label("teacher_name"),
                    Room.id.label("room_id"),
                    Room.name.label("room_name"),
                    Room.building.label("building"),
                    Section.id.label("section_id"),
                    Section.program.label("program"),
                    Section.batch.label("batch"),
                    Section.semester.label("semester"),
                    Section.section_type.label("section_type"),
                    Section.section_number.label("section_number"),
                    Course.id.label("course_id"),
                    Course.name.label("course_name"),
                    Course.code.label("course_code"),
                    TimeSlot.id.label("timeslot_id"),
                    TimeSlot.day.label("day"),
                    TimeSlot.start_time.label("start_time"),
                    TimeSlot.end_time.label("end_time"),
                )
                .join(Teacher,  Assignment.teacher_id  == Teacher.id)
                .join(Room,     Assignment.room_id     == Room.id)
                .join(Section,  Assignment.section_id  == Section.id)
                .join(Course,   Assignment.course_id   == Course.id)
                .join(TimeSlot, Assignment.timeslot_id == TimeSlot.id)
                .all()
            )

            self._assignments = [row._asdict() for row in rows]

            print(f"\n{'='*70}")
            print(f"[SEARCH] CONFLICT DETECTOR DEBUG OUTPUT")
            print(f"{'='*70}")
            print(f"[OK] Total assignments loaded from database: {len(self._assignments)}")

            if self._assignments:
                print(f"\n[LIST] Sample of first 3 assignments:")
                for i, a in enumerate(self._assignments[:3], 1):
                    print(f"  [{i}] {a['course_code']} | Teacher: {a['teacher_name']} | "
                          f"Room: {a['room_name']} | {a['day']} {a['start_time']}-{a['end_time']}")

                print(f"\n[SECURE] Data Integrity Checks:")
                print(f"  - All teacher_ids non-null: {all(a['teacher_id'] for a in self._assignments)}")
                print(f"  - All room_ids non-null:    {all(a['room_id']    for a in self._assignments)}")
                print(f"  - All section_ids non-null: {all(a['section_id'] for a in self._assignments)}")
                print(f"  - All timeslot_ids non-null:{all(a['timeslot_id']for a in self._assignments)}")
                print(f"  - All times valid HH:MM:    {all(self._is_valid_time(a['start_time']) for a in self._assignments)}")
            else:
                print("  [WARNING] No assignments loaded! Check database connection.")

        except Exception as e:
            print(f"  [ERROR] ERROR loading assignments: {e}")
            import traceback
            traceback.print_exc()
            self._assignments = []

    @staticmethod
    def _is_valid_time(time_str) -> bool:
        """Check if time string is valid HH:MM format."""
        if not time_str:
            return False
        try:
            parts = str(time_str).split(':')
            if len(parts) != 2:
                return False
            h, m = int(parts[0]), int(parts[1])
            return 0 <= h < 24 and 0 <= m < 60
        except Exception:
            return False

    # ── Helper: time overlap detection ────────────────────────────────────────

    @staticmethod
    def _times_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
        """Return True if two HH:MM time ranges overlap."""
        def to_minutes(t: str) -> int:
            h, m = map(int, t.split(":"))
            return h * 60 + m

        s1, e1 = to_minutes(start1), to_minutes(end1)
        s2, e2 = to_minutes(start2), to_minutes(end2)
        return s1 < e2 and s2 < e1

    @staticmethod
    def _gap_minutes(end_time: str, start_time: str) -> int:
        """Minutes between end of one slot and start of next."""
        def to_minutes(t: str) -> int:
            h, m = map(int, t.split(":"))
            return h * 60 + m
        return to_minutes(start_time) - to_minutes(end_time)

    @staticmethod
    def _slot_label(a: dict) -> str:
        return f"{a['start_time']}–{a['end_time']}"

    @staticmethod
    def _section_label(a: dict) -> str:
        return (f"{a['program']} SE {a['section_type']} "
                f"({a['batch']}) Sem#{a['semester']}")

    # ── Check 1: Teacher Double-Booking ───────────────────────────────────────

    def _check_teacher_double_booking(self):
        """CRITICAL: Same teacher, overlapping times, different rooms."""
        by_teacher_day: dict = defaultdict(list)
        for a in self._assignments:
            by_teacher_day[(a["teacher_id"], a["day"])].append(a)

        print(f"\n[SEARCH] Checking Teacher Double-Booking:")
        print(f"   Total (teacher_id, day) groups: {len(by_teacher_day)}")

        conflicts_found = 0
        for (tid, day), slots in by_teacher_day.items():
            if len(slots) > 1:
                print(f"   -> Checking {slots[0]['teacher_name']} on {day}: {len(slots)} assignments")

            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    a1, a2 = slots[i], slots[j]
                    if not (self._is_valid_time(a1["start_time"]) and
                            self._is_valid_time(a1["end_time"]) and
                            self._is_valid_time(a2["start_time"]) and
                            self._is_valid_time(a2["end_time"])):
                        continue
                    # SKIP combined classes: same teacher, same room, same time,
                    # different sections = intentional multi-section lecture
                    if (a1["room_id"] == a2["room_id"] and
                            a1["start_time"] == a2["start_time"] and
                            a1["end_time"] == a2["end_time"]):
                        continue
                    if self._times_overlap(a1["start_time"], a1["end_time"],
                                           a2["start_time"], a2["end_time"]):
                        conflicts_found += 1
                        print(f"     [!] CONFLICT: {a1['teacher_name']} @ "
                              f"{a1['start_time']}-{a1['end_time']} in {a1['room_name']} vs "
                              f"{a2['start_time']}-{a2['end_time']} in {a2['room_name']}")
                        self.report.add(Conflict(
                            conflict_type="Teacher Double-Booking",
                            severity="CRITICAL",
                            description=(
                                f"'{a1['teacher_name']}' is scheduled in BOTH "
                                f"'{a1['room_name']}' ({a1['course_code']}) AND "
                                f"'{a2['room_name']}' ({a2['course_code']}) "
                                f"at overlapping times."
                            ),
                            affected_ids=[a1["id"], a2["id"]],
                            day=day,
                            time_slot=f"{self._slot_label(a1)} / {self._slot_label(a2)}",
                            entity_name=a1["teacher_name"],
                        ))

        print(f"   [OK] Teacher conflicts found: {conflicts_found}")

    # ── Check 2: Room Double-Booking ──────────────────────────────────────────

    def _check_room_double_booking(self):
        """CRITICAL: Same room, overlapping times, different classes."""
        by_room_day: dict = defaultdict(list)
        for a in self._assignments:
            by_room_day[(a["room_id"], a["day"])].append(a)

        print(f"\n[SEARCH] Checking Room Double-Booking:")
        print(f"   Total (room_id, day) groups: {len(by_room_day)}")

        conflicts_found = 0
        for (rid, day), slots in by_room_day.items():
            if len(slots) > 1:
                print(f"   -> Checking {slots[0]['room_name']} on {day}: {len(slots)} assignments")

            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    a1, a2 = slots[i], slots[j]
                    if not (self._is_valid_time(a1["start_time"]) and
                            self._is_valid_time(a1["end_time"]) and
                            self._is_valid_time(a2["start_time"]) and
                            self._is_valid_time(a2["end_time"])):
                        continue
                    # SKIP combined classes: same course, same teacher, same room,
                    # same time but different sections = NOT a conflict
                    if (a1["course_id"] == a2["course_id"] and
                            a1["teacher_id"] == a2["teacher_id"] and
                            a1["start_time"] == a2["start_time"] and
                            a1["end_time"] == a2["end_time"]):
                        continue
                    if self._times_overlap(a1["start_time"], a1["end_time"],
                                           a2["start_time"], a2["end_time"]):
                        conflicts_found += 1
                        print(f"     [!] CONFLICT: Room {a1['room_name']} @ "
                              f"{a1['start_time']}-{a1['end_time']} ({a1['course_code']}) vs "
                              f"{a2['start_time']}-{a2['end_time']} ({a2['course_code']})")
                        self.report.add(Conflict(
                            conflict_type="Room Double-Booking",
                            severity="CRITICAL",
                            description=(
                                f"Room '{a1['room_name']}' is booked for BOTH "
                                f"'{a1['course_code']}' ({self._section_label(a1)}) "
                                f"AND '{a2['course_code']}' ({self._section_label(a2)}) "
                                f"at the same time."
                            ),
                            affected_ids=[a1["id"], a2["id"]],
                            day=day,
                            time_slot=f"{self._slot_label(a1)} / {self._slot_label(a2)}",
                            entity_name=a1["room_name"],
                        ))

        print(f"   [OK] Room conflicts found: {conflicts_found}")

    # ── Check 3: Section Double-Booking ───────────────────────────────────────

    def _check_section_double_booking(self):
        """HIGH: Same section has two classes at overlapping times."""
        by_section_day: dict = defaultdict(list)
        for a in self._assignments:
            by_section_day[(a["section_id"], a["day"])].append(a)

        print(f"\n[SEARCH] Checking Section Double-Booking:")
        print(f"   Total (section_id, day) groups: {len(by_section_day)}")

        conflicts_found = 0
        for (sid, day), slots in by_section_day.items():
            if len(slots) > 1:
                print(f"   -> Checking {self._section_label(slots[0])} on {day}: {len(slots)} assignments")

            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    a1, a2 = slots[i], slots[j]
                    if not (self._is_valid_time(a1["start_time"]) and
                            self._is_valid_time(a1["end_time"]) and
                            self._is_valid_time(a2["start_time"]) and
                            self._is_valid_time(a2["end_time"])):
                        continue
                    if self._times_overlap(a1["start_time"], a1["end_time"],
                                           a2["start_time"], a2["end_time"]):
                        conflicts_found += 1
                        print(f"     [!] CONFLICT: Section {self._section_label(a1)} @ "
                              f"{a1['start_time']}-{a1['end_time']} ({a1['course_code']}) vs "
                              f"{a2['start_time']}-{a2['end_time']} ({a2['course_code']})")
                        self.report.add(Conflict(
                            conflict_type="Section Double-Booking",
                            severity="HIGH",
                            description=(
                                f"Section '{self._section_label(a1)}' has overlapping classes: "
                                f"'{a1['course_code']}' and '{a2['course_code']}' at the same time."
                            ),
                            affected_ids=[a1["id"], a2["id"]],
                            day=day,
                            time_slot=f"{self._slot_label(a1)} / {self._slot_label(a2)}",
                            entity_name=self._section_label(a1),
                        ))

        print(f"   [OK] Section conflicts found: {conflicts_found}")

    # ── Check 4: Teacher Overload ──────────────────────────────────────────────

    def _check_teacher_overload(self):
        """MEDIUM: Teacher has more than MAX_CLASSES_PER_TEACHER_PER_DAY in one day."""
        by_teacher_day: dict = defaultdict(list)
        for a in self._assignments:
            by_teacher_day[(a["teacher_id"], a["day"])].append(a)

        for (tid, day), slots in by_teacher_day.items():
            if len(slots) > self.MAX_CLASSES_PER_TEACHER_PER_DAY:
                teacher_name = slots[0]["teacher_name"]
                courses = ", ".join(s["course_code"] for s in slots)
                self.report.add(Conflict(
                    conflict_type="Teacher Overload",
                    severity="MEDIUM",
                    description=(
                        f"'{teacher_name}' has {len(slots)} classes on {day} "
                        f"(limit: {self.MAX_CLASSES_PER_TEACHER_PER_DAY}). "
                        f"Courses: {courses}"
                    ),
                    affected_ids=[s["id"] for s in slots],
                    day=day,
                    time_slot=f"{len(slots)} classes",
                    entity_name=teacher_name,
                ))

    # ── Check 5: Back-to-Back with Travel ────────────────────────────────────

    def _check_back_to_back_travel(self):
        """LOW: Teacher must move between buildings with insufficient gap."""
        by_teacher_day: dict = defaultdict(list)
        for a in self._assignments:
            by_teacher_day[(a["teacher_id"], a["day"])].append(a)

        for (tid, day), slots in by_teacher_day.items():
            sorted_slots = sorted(slots, key=lambda x: x["start_time"])
            for i in range(len(sorted_slots) - 1):
                a1 = sorted_slots[i]
                a2 = sorted_slots[i + 1]

                gap = self._gap_minutes(a1["end_time"], a2["start_time"])
                different_buildings = (
                    a1["building"] and a2["building"] and
                    a1["building"] != a2["building"]
                )

                if different_buildings and 0 < gap < self.TRAVEL_TIME_MINUTES:
                    self.report.add(Conflict(
                        conflict_type="Back-to-Back Travel Conflict",
                        severity="LOW",
                        description=(
                            f"'{a1['teacher_name']}' finishes '{a1['course_code']}' "
                            f"in {a1['building']} at {a1['end_time']} but must be in "
                            f"{a2['building']} for '{a2['course_code']}' at {a2['start_time']} "
                            f"— only {gap} min gap, need {self.TRAVEL_TIME_MINUTES} min."
                        ),
                        affected_ids=[a1["id"], a2["id"]],
                        day=day,
                        time_slot=f"{a1['end_time']} → {a2['start_time']} ({gap} min gap)",
                        entity_name=a1["teacher_name"],
                    ))

    # ── Check 6: Long Day for Section ────────────────────────────────────────

    def _check_section_long_day(self):
        """LOW: Section has more than MAX_CLASSES_PER_SECTION_PER_DAY in one day."""
        by_section_day: dict = defaultdict(list)
        for a in self._assignments:
            by_section_day[(a["section_id"], a["day"])].append(a)

        for (sid, day), slots in by_section_day.items():
            if len(slots) > self.MAX_CLASSES_PER_SECTION_PER_DAY:
                label   = self._section_label(slots[0])
                courses = ", ".join(s["course_code"] for s in slots)
                self.report.add(Conflict(
                    conflict_type="Section Long Day",
                    severity="LOW",
                    description=(
                        f"Section '{label}' has {len(slots)} classes on {day} "
                        f"(limit: {self.MAX_CLASSES_PER_SECTION_PER_DAY}). "
                        f"Courses: {courses}"
                    ),
                    affected_ids=[s["id"] for s in slots],
                    day=day,
                    time_slot=f"{len(slots)} classes",
                    entity_name=label,
                ))