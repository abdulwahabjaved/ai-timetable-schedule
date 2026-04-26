"""
Timetable Conflict Analysis - Accurate breakdown
Separates REAL conflicts from combined classes
"""

# REAL ROOM CONFLICTS (different courses or different teachers, same room, overlapping time)
room_conflicts_real = [
    ("NAB CR-224", "Saturday", "SECC-703 (Dr. Summair Raza) vs SEEC-705 (Dr. Ramzan)", "10:00-13:00"),
    ("NAB CR-232", "Monday", "CMPC-301 (Hadia) vs SECC-301 (Iqra Mushtaq)", "08:00-09:30"),
    ("NAB CR-232", "Monday", "CMPC-5209 (Mavra) vs MATH-5101 (M. Umer Iqbal)", "14:00-15:30 overlap"),
    ("NAB CR-233", "Tuesday", "SEEC-409 (Anila Sajid) vs CMPC-302 (Mehwish)", "14:00-15:30"),
    ("NAB CR-234", "Tuesday", "SEDC-5101 (Memoona) vs MATH-5102 (Ehsan)", "14:00-15:30"),
    ("NAB CR-237", "Monday", "CMPC-5207 (Ms. Usma) vs SEEC-419 (Saima Aslam)", "14:00-15:30"),
    ("NAB CR-238", "Thursday", "URCQ-5111 (Abu Sufyan) vs CMPC-5101 (Ms. Usma)", "14:00-16:00 overlap"),
    ("NAB CR-239", "Thursday", "CMPC-5209 Mavra Abbas vs CMPC-5209 Umme Aeman", "14:00-15:30"),
    ("NAB CR-241", "Friday", "SECC-301 (Iqra Mushtaq) vs MATH-5101 (Ehsan)", "12:30-14:00"),
]

# COMBINED CLASSES - Same course, same teacher, same room, same time, different sections
# These are INTENTIONAL - teacher teaches multiple sections together. NOT conflicts!
combined_classes = [
    ("Education Hall", "Wednesday", "URCG-5105 x2 sections - M. Umar Nissar Malik"),
    ("Education Hall", "Thursday", "URCG-5105 x2 sections - Zulfiqar Ali"),
    ("Education Hall", "Saturday", "URCG-5129 x2 sections - Abdul Satar"),
    ("NAB CR-226", "Tuesday 08:00", "URCM-5108 x3 sections - Dr. Syed Ali Haider Shah"),
    ("NAB CR-226", "Tuesday 09:30", "URCM-5108 x3 sections - Dr. Syed Ali Haider Shah"),
    ("NAB Hall-2", "Saturday", "URCC-5110 x3 sections - Anoosha Maryem"),
    ("Pharmacy Hall", "Monday", "URCG-5105 x2 sections - Hussain Akram"),
    ("Pharmacy Hall", "Wednesday", "URCG-5129 x3 sections - Ameer Hamza"),
    ("Pharmacy Hall", "Friday", "URCG-5119 x2 sections - Sana Batool"),
    ("Physics Hall", "Thursday", "URCG-5122 x2 sections - Usman Sagheer"),
    ("Physics Hall", "Friday", "URCG-5128 x2 sections - Khalil Shah"),
    ("Physics Hall", "Saturday", "URCG-5111 x2 sections - Khuram Shahzad"),
]

# TEACHER CONFLICTS (same teacher, different rooms, overlapping time)
teacher_conflicts = [
    ("Areeba Shahzad", "Wednesday", "NAB CR-233 (BUSB-201) vs MAB L-03 (BUSB-201)", "11:00-12:30"),
    ("Iqra Mushtaq", "Wednesday", "NAB CR-238 (SEEC-301 14:00) vs NAB CR-239 (SEDC-5201 14:00)", "14:00-15:30"),
    ("Iqra Mushtaq", "Wednesday", "NAB CR-238 (SEEC-301 14:00) vs MAB L-03 (CMPC-5207 15:00)", "overlap"),
    ("Iqra Mushtaq", "Wednesday", "NAB CR-239 (SEDC-5201 14:00) vs MAB L-03 (CMPC-5207 15:00)", "overlap"),
    ("Iqra Mushtaq", "Wednesday", "NAB CR-239 (SEDC-5201 15:30) vs MAB L-03 (CMPC-5207 15:00)", "overlap"),
    ("Kashaf Hassan", "Tuesday", "ARB CR-219 (13:00-14:00) vs MAB L-03 (12:00-13:30)", "overlap"),
    ("Mavra Abbas", "Monday", "NAB CR-224 (13:30-14:30) vs NAB CR-232 (14:00-15:00)", "overlap"),
    ("Mavra Abbas", "Tuesday", "ARB CR-221 (15:00-16:00) vs ARB L-10 (14:30-16:00)", "overlap"),
    ("Ms Hafiza Anila Sajid", "Tuesday", "NAB CR-233 (SEEC-409) vs NAB CR-240 (SEEC-409)", "14:00-15:30"),
    ("Quasira Ramzan", "Tuesday", "NAB CR-226 (SECC-302 15:30) vs NAB CR-241 (SESC-305 15:30)", "15:30-17:00"),
    ("Umme Aeman", "Monday", "NAB CR-225 (15:30-16:30) vs NAB CR-232 (15:30-16:30)", "overlap"),
    ("Umme Aeman", "Monday", "NAB CR-226 (13:30-15:00) vs NAB CR-235 (14:00-15:00)", "overlap"),
]

print("=" * 70)
print("   ACCURATE TIMETABLE CONFLICT ANALYSIS")
print("   Department of Software Engineering")
print("=" * 70)

print(f"\n{'='*70}")
print(f"  REAL ROOM CONFLICTS: {len(room_conflicts_real)}")
print(f"{'='*70}")
for i, (room, day, desc, time) in enumerate(room_conflicts_real, 1):
    print(f"  {i:2d}. [{room}] {day}")
    print(f"      {desc}")
    print(f"      Time: {time}")
    print()

print(f"{'='*70}")
print(f"  COMBINED CLASSES (NOT conflicts): {len(combined_classes)}")
print(f"{'='*70}")
for i, (room, day, desc) in enumerate(combined_classes, 1):
    print(f"  {i:2d}. [{room}] {day} - {desc}")

print(f"\n{'='*70}")
print(f"  TEACHER CONFLICTS: {len(teacher_conflicts)}")
print(f"{'='*70}")
for i, (teacher, day, desc, time) in enumerate(teacher_conflicts, 1):
    print(f"  {i:2d}. [{teacher}] {day}")
    print(f"      {desc}")
    print()

sep = "=" * 70
print(f"\n{sep}")
print("  FINAL SUMMARY")
print(sep)
print(f"  Total entries in timetable:   277")
print(f"  Real Room Conflicts:          {len(room_conflicts_real)}")
print(f"  Real Teacher Conflicts:       {len(teacher_conflicts)}")
total = len(room_conflicts_real) + len(teacher_conflicts)
print(f"  TOTAL REAL CONFLICTS:         {total}")
print(f"  Combined classes (OK):        {len(combined_classes)}")
print(sep)
print(f"  Previous system said:         114 conflicts  --> GHALAT (wrong)")
print(f"  Previous Claude said:         41 conflicts   --> Partially correct")  
print(f"  Actual real conflicts:        {total} conflicts  --> SAHI (correct)")
print(sep)
print(f"\n  114 itne zyada isliye nikle kyunki:")
print(f"  - Combined classes ko bhi conflict mana (12 false positives)")
print(f"  - Section overload ko bhi count kiya")
print(f"  - Duplicate entries ko multiply count kiya")
print(f"  - Har pair ko alag conflict gina (3 sections = 3 pairs = 3 conflicts)")
