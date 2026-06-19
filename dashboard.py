from typing import Dict, Any, List
from telegram import ReplyKeyboardMarkup
from database import Database
from logger import setup_logger

logger = setup_logger(__name__)


def build_course_dashboard(user_id: int, db: Database) -> str:
    courses = db.get_all_user_courses(user_id)
    lines = ["📊 YOUR COURSES"]
    if not courses:
        lines.append("No active courses yet. Start a new course below.")
    else:
        for course in courses:
            lines.append("────────────────────────")
            lines.append(f"🐍 {course.get('fan')} | {course.get('daraja')}")
            lines.append(f"Progress: Day {course.get('current_kun')}/{course.get('total_days')} ({course.get('progress_percent', 0)}%)")
            lines.append(f"Status: {course.get('status')} | Last: {course.get('last_accessed_at') or 'N/A'}")
    lines.append("────────────────────────")
    return "\n".join(lines)


def course_menu_markup(courses: List[Dict[str, Any]]) -> ReplyKeyboardMarkup:
    buttons = []
    for course in courses[:4]:
        status = course.get("status", "ACTIVE")
        if status == "ACTIVE":
            label = f"⏸️ PAUSE {course['course_id']}: {course['fan']}"
        elif status == "PAUSED":
            label = f"▶️ RESUME {course['course_id']}: {course['fan']}"
        elif status == "ABANDONED":
            label = f"🗑️ DELETE {course['course_id']}: {course['fan']}"
        else:
            label = f"📖 {course['course_id']}: {course['fan']} ({status})"
        buttons.append([label])
    buttons.append(["➕ START NEW COURSE"])
    buttons.append(["📊 STATISTICS", "⚙️ SETTINGS"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def build_statistics_text(user_id: int, db: Database) -> str:
    stats = db.get_user_stats(user_id)
    active = db.get_active_course(user_id)
    lines: List[str] = []
    lines.append("📈 OVERALL:")
    lines.append(f"- Total courses: {stats.get('total_courses', 0)}")
    lines.append(f"- Completed: {stats.get('completed_courses', 0)}")
    lines.append("")
    if active:
        lines.append("📚 CURRENT COURSE:")
        lines.append(f"- Subject: {active.get('fan')}")
        lines.append(f"- Progress: {active.get('current_kun')}/{active.get('total_days')} days")
    return "\n".join(lines)
