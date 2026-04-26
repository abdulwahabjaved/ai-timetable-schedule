# AI Timetable System v1.0

A Flask-based web application designed to automatically parse, manage, and detect conflicts in university timetables. Built specifically for the Software Engineering Department.

## Features

- **Upload-Driven Architecture:** Upload your timetable data directly via PDF or CSV files.
- **Smart Parsing:** Automatically extracts courses, teachers, rooms, and class sections using robust regex-based text block parsing.
- **Advanced Conflict Detection:** 
  - Teacher Double-Booking Detection
  - Room Double-Booking Detection
  - Section Double-Booking Detection
  - Intelligently skips combined classes (same course, teacher, room, and time across multiple sections).
- **Interactive Timetable Grid:** View your parsed schedules in a clean, visual weekly grid format.
- **Dashboard & Analytics:** Get an overview of all entities (Teachers, Rooms, Courses, Sections, and Assignments) and their potential scheduling conflicts.

## Tech Stack

- **Backend:** Python, Flask, SQLAlchemy (SQLite database)
- **Frontend:** HTML5, CSS3 (Vanilla), Jinja2 Templating
- **PDF Parsing:** `pdfplumber`

## Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd ai_timetable
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python run.py
   ```

5. **Access the application:**
   Open your browser and navigate to `http://127.0.0.1:5000`

## Usage Guide

1. Go to the **Upload** page.
2. Upload your departmental timetable in either `.pdf` or `.csv` format.
3. Once uploaded, the system will clear any existing data and parse the new file.
4. Navigate to the **Conflicts** page to see if any teachers, rooms, or sections have overlapping schedules.
5. Go to the **Timetable** page to see the visual representation of all parsed classes.

## Version

**v1.0** - Initial stable release featuring PDF/CSV uploading, full database integration, and conflict resolution analytics.
