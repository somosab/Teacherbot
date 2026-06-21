from typing import Optional, Dict, Any
from database import Database
from logger import setup_logger

logger = setup_logger(__name__)


def get_resume_message(user_id: int, db: Database) -> Optional[Dict[str, Any]]:
    """Return a dictionary describing where the user left off, or None."""
    session = db.get_session(user_id)
    if not session:
        return None
    course = db.get_course(session.get("course_id")) if session.get("course_id") else None
    return {
        "course": course,
        "last_kun": session.get("last_accessed_kun"),
        "last_post": session.get("last_accessed_post"),
        "status": session.get("status"),
    }


def resume_available(user_id: int, db: Database) -> bool:
    return db.get_session(user_id) is not None


def save_session_state(user_id: int, course_id: int, kun: int, post: int, db: Database) -> None:
    try:
        db.save_session(user_id=user_id, course_id=course_id, kun=kun, post=post)
        logger.info("Saved session for user %s course %s kun=%s post=%s", user_id, course_id, kun, post)
    except Exception:
        logger.exception("Failed to save session for user %s", user_id)


def clear_session(user_id: int, db: Database) -> None:
    try:
        db.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        logger.info("Cleared session for user %s", user_id)
    except Exception:
        logger.exception("Failed to clear session for user %s", user_id)
