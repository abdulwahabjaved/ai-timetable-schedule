# solver.py — AI Conflict Resolution Engine
from app.conflict_detector import ConflictDetector, ConflictReport
from app.models import db, Assignment

class ConflictSolver:
    """
    Takes detected conflicts and generates AI-based solutions.
    Future upgrade: auto-re-schedule timetable.
    """

    def __init__(self):
        self.detector = ConflictDetector()
        self.report = None

    def analyze(self) -> ConflictReport:
        """Run detection first"""
        self.report = self.detector.run()
        return self.report

    # ─────────────────────────────────────────────
    # AI Suggestions Engine
    # ─────────────────────────────────────────────

    def suggest_fixes(self):
        """
        Returns smart suggestions instead of only reporting errors.
        """
        if not self.report:
            self.analyze()

        suggestions = []

        for conflict in self.report.conflicts:

            # ── Teacher Double Booking ──
            if conflict.conflict_type == "Teacher Double-Booking":
                suggestions.append({
                    "issue": conflict.description,
                    "solution": "Reschedule one class to another available time slot for the teacher.",
                    "priority": "CRITICAL"
                })

            # ── Room Conflict ──
            elif conflict.conflict_type == "Room Double-Booking":
                suggestions.append({
                    "issue": conflict.description,
                    "solution": "Assign one class to a different available room in same time slot.",
                    "priority": "CRITICAL"
                })

            # ── Section Conflict ──
            elif conflict.conflict_type == "Section Double-Booking":
                suggestions.append({
                    "issue": conflict.description,
                    "solution": "Split section or move one course to free slot.",
                    "priority": "HIGH"
                })

            # ── Teacher Overload ──
            elif conflict.conflict_type == "Teacher Overload":
                suggestions.append({
                    "issue": conflict.description,
                    "solution": "Redistribute classes among visiting teachers or shift to alternate days.",
                    "priority": "MEDIUM"
                })

            # ── Travel Issue ──
            elif "Travel" in conflict.conflict_type:
                suggestions.append({
                    "issue": conflict.description,
                    "solution": "Increase gap between classes or assign nearby building rooms.",
                    "priority": "LOW"
                })

        return suggestions

    # ─────────────────────────────────────────────
    # Future Upgrade Hook (AI Auto Scheduler)
    # ─────────────────────────────────────────────

    def auto_fix(self):
        """
        Future: AI will automatically fix timetable conflicts.
        (You can integrate Genetic Algorithm or Reinforcement Learning here)
        """
        return {
            "status": "coming_soon",
            "message": "Auto-scheduling AI will be implemented in next version."
        }