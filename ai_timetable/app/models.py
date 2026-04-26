"""
models.py — SQLAlchemy database models for AI Timetable System
SE Department, University of Sargodha

No functional changes from original — included here as complete reference
so all four files are consistent and ready to drop in together.
"""

from app import db
from datetime import datetime


class Teacher(db.Model):
    __tablename__ = 'teachers'

    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(120), nullable=False, unique=True)
    type               = db.Column(db.String(20), default='Visiting')   # Regular / Visiting
    email              = db.Column(db.String(120), nullable=True)
    max_hours_per_week = db.Column(db.Integer, default=18)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('Assignment', back_populates='teacher',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Teacher {self.name} ({self.type})>'

    def to_dict(self):
        return {
            'id':                 self.id,
            'name':               self.name,
            'type':               self.type,
            'email':              self.email,
            'max_hours_per_week': self.max_hours_per_week,
        }


class Room(db.Model):
    __tablename__ = 'rooms'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(60),  nullable=False, unique=True)
    building   = db.Column(db.String(60),  nullable=True)
    capacity   = db.Column(db.Integer, default=40)
    room_type  = db.Column(db.String(20),  default='Classroom')  # Classroom / Lab / Hall
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('Assignment', back_populates='room',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Room {self.name}>'

    def to_dict(self):
        return {
            'id':        self.id,
            'name':      self.name,
            'building':  self.building,
            'capacity':  self.capacity,
            'room_type': self.room_type,
        }


class Course(db.Model):
    __tablename__ = 'courses'

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(30),  nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    credit_hours = db.Column(db.Integer, default=3)
    course_type = db.Column(db.String(20),  default='Core')  # Core / Elective / Lab
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('Assignment', back_populates='course',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Course {self.code}: {self.name}>'

    def to_dict(self):
        return {
            'id':           self.id,
            'code':         self.code,
            'name':         self.name,
            'credit_hours': self.credit_hours,
            'course_type':  self.course_type,
        }


class Section(db.Model):
    __tablename__ = 'sections'

    id             = db.Column(db.Integer, primary_key=True)
    program        = db.Column(db.String(60), nullable=False)   # BS / MS
    batch          = db.Column(db.String(20), nullable=False)   # e.g. "2025-2029"
    semester       = db.Column(db.Integer,    nullable=False)   # 1-8
    section_type   = db.Column(db.String(20), default='Regular')  # Regular / Self Support
    section_number = db.Column(db.Integer,    default=1)
    student_count  = db.Column(db.Integer,    default=40)
    created_at     = db.Column(db.DateTime,   default=datetime.utcnow)

    assignments = db.relationship('Assignment', back_populates='section',
                                  cascade='all, delete-orphan')

    @property
    def label(self):
        return (f"{self.program} {self.section_type} {self.section_number} "
                f"({self.batch}) Sem#{self.semester}")

    def __repr__(self):
        return f'<Section {self.label}>'

    def to_dict(self):
        return {
            'id':             self.id,
            'program':        self.program,
            'batch':          self.batch,
            'semester':       self.semester,
            'section_type':   self.section_type,
            'section_number': self.section_number,
            'label':          self.label,
        }


class TimeSlot(db.Model):
    __tablename__ = 'timeslots'

    id         = db.Column(db.Integer, primary_key=True)
    day        = db.Column(db.String(10), nullable=False)   # Monday, Tuesday, ...
    start_time = db.Column(db.String(6),  nullable=False)   # "08:00"
    end_time   = db.Column(db.String(6),  nullable=False)   # "09:30"

    assignments = db.relationship('Assignment', back_populates='timeslot',
                                  cascade='all, delete-orphan')

    @property
    def duration_minutes(self):
        sh, sm = map(int, self.start_time.split(':'))
        eh, em = map(int, self.end_time.split(':'))
        return (eh * 60 + em) - (sh * 60 + sm)

    def __repr__(self):
        return f'<TimeSlot {self.day} {self.start_time}-{self.end_time}>'

    def to_dict(self):
        return {
            'id':               self.id,
            'day':              self.day,
            'start_time':       self.start_time,
            'end_time':         self.end_time,
            'duration_minutes': self.duration_minutes,
        }


class Assignment(db.Model):
    """
    Core table — one row = one class session scheduled.
    Represents: Course X taught by Teacher Y in Room Z for Section S at TimeSlot T.
    """
    __tablename__ = 'assignments'

    id          = db.Column(db.Integer, primary_key=True)
    course_id   = db.Column(db.Integer, db.ForeignKey('courses.id'),   nullable=False)
    teacher_id  = db.Column(db.Integer, db.ForeignKey('teachers.id'),  nullable=False)
    room_id     = db.Column(db.Integer, db.ForeignKey('rooms.id'),     nullable=False)
    section_id  = db.Column(db.Integer, db.ForeignKey('sections.id'),  nullable=False)
    timeslot_id = db.Column(db.Integer, db.ForeignKey('timeslots.id'), nullable=False)
    is_combined = db.Column(db.Boolean, default=False)
    source      = db.Column(db.String(20), default='parsed')  # parsed / generated / manual
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    course   = db.relationship('Course',   back_populates='assignments')
    teacher  = db.relationship('Teacher',  back_populates='assignments')
    room     = db.relationship('Room',     back_populates='assignments')
    section  = db.relationship('Section',  back_populates='assignments')
    timeslot = db.relationship('TimeSlot', back_populates='assignments')

    def __repr__(self):
        return f'<Assignment {self.course.code if self.course else "?"} @ {self.timeslot}>'

    def to_dict(self):
        return {
            'id':          self.id,
            'course':      self.course.to_dict()   if self.course   else None,
            'teacher':     self.teacher.to_dict()  if self.teacher  else None,
            'room':        self.room.to_dict()     if self.room     else None,
            'section':     self.section.to_dict()  if self.section  else None,
            'timeslot':    self.timeslot.to_dict() if self.timeslot else None,
            'is_combined': self.is_combined,
            'source':      self.source,
        }


class Conflict(db.Model):
    """Stores detected conflicts for reporting and resolution."""
    __tablename__ = 'conflicts'

    id              = db.Column(db.Integer, primary_key=True)
    conflict_type   = db.Column(db.String(30),  nullable=False)
    severity        = db.Column(db.String(10),  default='HIGH')
    description     = db.Column(db.String(300), nullable=False)
    assignment_1_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=True)
    assignment_2_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=True)
    is_resolved     = db.Column(db.Boolean, default=False)
    detected_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':            self.id,
            'conflict_type': self.conflict_type,
            'severity':      self.severity,
            'description':   self.description,
            'is_resolved':   self.is_resolved,
        }