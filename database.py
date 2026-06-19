import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from logger import setup_logger

logger = setup_logger(__name__)


class Database:
    """SQLite-backed persistence for TeacherBot courses."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                lang TEXT DEFAULT 'uz',
                fan TEXT,
                daraja TEXT,
                maqsad TEXT,
                vaqt TEXT,
                kun INTEGER DEFAULT 1,
                current_post INTEGER DEFAULT 1,
                lesson_total_posts INTEGER DEFAULT 1,
                next_day_unlock TEXT,
                state TEXT,
                last_lesson TEXT,
                last_active TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_courses (
                course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                fan TEXT,
                daraja TEXT,
                maqsad TEXT,
                vaqt TEXT,
                current_kun INTEGER DEFAULT 1,
                current_post INTEGER DEFAULT 1,
                total_days INTEGER DEFAULT 30,
                total_posts_per_day INTEGER DEFAULT 1,
                status TEXT DEFAULT 'ACTIVE',
                progress_percent REAL DEFAULT 0,
                quiz_score_average REAL DEFAULT 0,
                homework_completion REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TEXT,
                completed_at TEXT,
                paused_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS course_lessons (
                lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                kun INTEGER NOT NULL,
                post_num INTEGER NOT NULL,
                content TEXT NOT NULL,
                quiz_questions TEXT,
                homework TEXT,
                saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(course_id, kun, post_num),
                FOREIGN KEY(course_id) REFERENCES user_courses(course_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS course_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                kun INTEGER NOT NULL,
                post_num INTEGER NOT NULL,
                user_understood INTEGER DEFAULT 1,
                quiz_score REAL,
                homework_submitted INTEGER DEFAULT 0,
                homework_content TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(course_id) REFERENCES user_courses(course_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER,
                accessed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                action TEXT,
                last_accessed_kun INTEGER DEFAULT 1,
                last_accessed_post INTEGER DEFAULT 1,
                status TEXT DEFAULT 'IN_PROGRESS',
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(course_id) REFERENCES user_courses(course_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                course_id INTEGER,
                kun INTEGER,
                question_num INTEGER,
                answer TEXT,
                is_correct INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(course_id) REFERENCES user_courses(course_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kun INTEGER,
                fan TEXT,
                content TEXT,
                saved_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self.connection.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {key: row[key] for key in row.keys()} if row else {}

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def ensure_user(self, user_id: int, lang: Optional[str] = None) -> None:
        now = datetime.utcnow().isoformat()
        cursor = self.connection.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        if not exists:
            self.execute(
                "INSERT INTO users (user_id, lang, last_active) VALUES (?, ?, ?)",
                (user_id, lang or "uz", now),
            )
        else:
            self.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id))

    def upsert_user(self, user_id: int, **kwargs) -> int:
        allowed = [
            "lang",
            "fan",
            "daraja",
            "maqsad",
            "vaqt",
            "kun",
            "current_post",
            "lesson_total_posts",
            "next_day_unlock",
            "state",
            "last_lesson",
        ]
        data = {k: kwargs[k] for k in allowed if k in kwargs}
        now = datetime.utcnow().isoformat()
        data["last_active"] = now

        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        update_parts = ", ".join(f"{k}=excluded.{k}" for k in data.keys())

        sql = (
            f"INSERT INTO users (user_id, {cols}) VALUES (?, {placeholders}) "
            f"ON CONFLICT(user_id) DO UPDATE SET {update_parts}"
        )
        params = (user_id, *tuple(data.values()))

        try:
            self.execute(sql, params)
            logger.info("Upserted user %s fields=%s", user_id, list(data.keys()))
            return user_id
        except Exception:
            logger.exception("Failed to upsert user %s", user_id)
            raise

    def create_course(
        self,
        user_id: int,
        fan: str,
        daraja: str,
        maqsad: str,
        vaqt: str,
        total_days: Optional[int] = None,
        total_posts_per_day: Optional[int] = None,
    ) -> int:
        now = datetime.utcnow().isoformat()
        total_days = total_days if total_days is not None else self._calculate_total_days(fan)
        total_posts_per_day = total_posts_per_day if total_posts_per_day is not None else self._calculate_total_posts(vaqt)

        cur = self.execute(
            """
            INSERT INTO user_courses (
                user_id, fan, daraja, maqsad, vaqt,
                current_kun, current_post, total_days, total_posts_per_day,
                status, progress_percent, quiz_score_average, homework_completion,
                created_at, last_accessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                fan,
                daraja,
                maqsad,
                vaqt,
                1,
                1,
                total_days,
                total_posts_per_day,
                "ACTIVE",
                0.0,
                0.0,
                0.0,
                now,
                now,
            ),
        )
        course_id = cur.lastrowid
        self.record_session(user_id, course_id, "START_COURSE")
        logger.info("Created course %s for user %s", course_id, user_id)
        return course_id

    def _calculate_total_posts(self, vaqt: str) -> int:
        mapping = {
            "⚡ 15 daqiqa": 1,
            "📖 30 daqiqa": 2,
            "💪 1 soat": 3,
            "🔥 2 soat+": 4,
        }
        return mapping.get(vaqt, 2)

    def _calculate_total_days(self, fan: str) -> int:
        mapping = {
            "Python": 30,
            "JavaScript": 30,
            "Math": 25,
            "Design": 20,
        }
        return mapping.get(fan, 30)

    def get_all_user_courses(self, user_id: int) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT course_id, fan, daraja, maqsad, vaqt, current_kun, current_post,
                   total_days, total_posts_per_day, status, progress_percent,
                   created_at, last_accessed_at, completed_at
            FROM user_courses
            WHERE user_id = ?
            ORDER BY last_accessed_at DESC
            """,
            (user_id,),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_course(self, course_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM user_courses WHERE course_id = ?", (course_id,))
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def get_active_course(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM user_courses WHERE user_id = ? AND status = 'ACTIVE' ORDER BY last_accessed_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def get_course_progress(self, course_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT current_kun, current_post, status, last_accessed_at, total_days, total_posts_per_day FROM user_courses WHERE course_id = ?",
            (course_id,),
        )
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def resume_course(self, user_id: int, course_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        course = self.get_course(course_id) if course_id else self.get_active_course(user_id)
        if not course:
            return None
        self.record_session(user_id, course["course_id"], "CONTINUE_COURSE")
        return {
            "course_id": course["course_id"],
            "fan": course["fan"],
            "daraja": course["daraja"],
            "maqsad": course["maqsad"],
            "vaqt": course["vaqt"],
            "current_kun": course["current_kun"],
            "current_post": course["current_post"],
            "total_days": course["total_days"],
            "total_posts_per_day": course["total_posts_per_day"],
            "status": course["status"],
            "progress_percent": course["progress_percent"],
        }

    def get_course_lesson(self, course_id: int, kun: int, post_num: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM course_lessons WHERE course_id = ? AND kun = ? AND post_num = ?",
            (course_id, kun, post_num),
        )
        row = cursor.fetchone()
        if not row:
            return None
        result = self._row_to_dict(row)
        if result.get("quiz_questions"):
            try:
                result["quiz_questions"] = json.loads(result["quiz_questions"])
            except Exception:
                result["quiz_questions"] = []
        return result

    def save_course_lesson(
        self,
        course_id: int,
        kun: int,
        post_num: int,
        content: str,
        quiz_questions: Optional[List[Dict[str, Any]]] = None,
        homework: Optional[str] = None,
    ) -> int:
        existing = self.get_course_lesson(course_id, kun, post_num)
        if existing:
            logger.info("Course lesson already exists course=%s kun=%s post=%s", course_id, kun, post_num)
            return existing["lesson_id"]

        quiz_json = json.dumps(quiz_questions or [])
        now = datetime.utcnow().isoformat()
        cur = self.execute(
            """
            INSERT INTO course_lessons (course_id, kun, post_num, content, quiz_questions, homework, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (course_id, kun, post_num, content, quiz_json, homework, now),
        )
        lesson_id = cur.lastrowid
        logger.info("Saved course lesson %s for course %s day %s post %s", lesson_id, course_id, kun, post_num)
        return lesson_id

    def update_course_progress(self, course_id: int, kun: int, post_num: int, understood: bool = True) -> None:
        course = self.get_course(course_id)
        if not course:
            raise ValueError(f"Course {course_id} not found")

        total_days = int(course.get("total_days", 30))
        total_posts = int(course.get("total_posts_per_day", 1))
        status = course.get("status", "ACTIVE")
        completed_at = course.get("completed_at")
        now = datetime.utcnow().isoformat()

        if kun > total_days or (kun == total_days and post_num > total_posts):
            kun = total_days
            post_num = total_posts
            status = "COMPLETED"
            completed_at = now
        elif status == "COMPLETED":
            status = "COMPLETED"
        else:
            status = "ACTIVE"

        progress_percent = round(((kun - 1) + (post_num / total_posts)) / total_days * 100, 1) if total_days > 0 else 0.0

        self.execute(
            """
            UPDATE user_courses
            SET current_kun = ?, current_post = ?, last_accessed_at = ?, progress_percent = ?, status = ?, completed_at = ?
            WHERE course_id = ?
            """,
            (kun, post_num, now, progress_percent, status, completed_at, course_id),
        )

        self.execute(
            """
            INSERT INTO course_progress (course_id, kun, post_num, user_understood, quiz_score, homework_submitted, homework_content, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (course_id, kun, post_num, int(bool(understood)), None, 0, None, now),
        )
        logger.info("Updated course progress for course %s kun=%s post=%s status=%s", course_id, kun, post_num, status)

    def pause_course(self, user_id: int, course_id: int) -> None:
        now = datetime.utcnow().isoformat()
        self.execute(
            "UPDATE user_courses SET status = 'PAUSED', last_accessed_at = ? WHERE course_id = ? AND user_id = ?",
            (now, course_id, user_id),
        )
        self.record_session(user_id, course_id, "PAUSE_COURSE")
        logger.info("Paused course %s for user %s", course_id, user_id)

    def complete_course(self, user_id: int, course_id: int) -> None:
        now = datetime.utcnow().isoformat()
        self.execute(
            "UPDATE user_courses SET status = 'COMPLETED', completed_at = ?, last_accessed_at = ? WHERE course_id = ? AND user_id = ?",
            (now, now, course_id, user_id),
        )
        self.record_session(user_id, course_id, "COMPLETE_COURSE")
        logger.info("Completed course %s for user %s", course_id, user_id)

    def delete_course(self, user_id: int, course_id: int) -> None:
        now = datetime.utcnow().isoformat()
        self.execute(
            "UPDATE user_courses SET status = 'ABANDONED', last_accessed_at = ? WHERE course_id = ? AND user_id = ?",
            (now, course_id, user_id),
        )
        self.record_session(user_id, course_id, "DELETE_COURSE")
        logger.info("Abandoned course %s for user %s", course_id, user_id)

    def record_session(
        self,
        user_id: int,
        course_id: int,
        action: str,
        last_accessed_kun: Optional[int] = None,
        last_accessed_post: Optional[int] = None,
        status: str = 'IN_PROGRESS',
    ) -> int:
        now = datetime.utcnow().isoformat()
        cur = self.execute(
            "INSERT INTO user_sessions (user_id, course_id, accessed_at, action, last_accessed_kun, last_accessed_post, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                course_id,
                now,
                action,
                last_accessed_kun or 1,
                last_accessed_post or 1,
                status,
            ),
        )
        return cur.lastrowid

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM user_sessions WHERE user_id = ? ORDER BY accessed_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def save_session(self, user_id: int, course_id: int, kun: int, post: int, status: str = 'IN_PROGRESS') -> int:
        return self.record_session(
            user_id=user_id,
            course_id=course_id,
            action=status,
            last_accessed_kun=kun,
            last_accessed_post=post,
            status=status,
        )

    def list_user_courses(self, user_id: int) -> List[Dict[str, Any]]:
        return self.get_all_user_courses(user_id)

    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total_courses, SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_courses FROM user_courses WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        return {
            "total_courses": row[0] or 0,
            "completed_courses": row[1] or 0,
        }

    def increment_completed_lessons(self, user_id: int) -> None:
        active_course = self.get_active_course(user_id)
        if active_course:
            next_kun = int(active_course.get("current_kun", 1)) + 1
            self.execute(
                "UPDATE user_courses SET current_kun = ?, current_post = 1, last_accessed_at = ? WHERE course_id = ?",
                (next_kun, datetime.utcnow().isoformat(), active_course["course_id"]),
            )
        else:
            self.execute(
                "UPDATE users SET kun = kun + 1, current_post = 1, last_active = ? WHERE user_id = ?",
                (datetime.utcnow().isoformat(), user_id),
            )

    def save_quiz_answer(self, user_id: int, course_id: int, kun: int, question_num: int, answer: str, is_correct: bool) -> int:
        cur = self.execute(
            "INSERT INTO quiz_answers (user_id, course_id, kun, question_num, answer, is_correct, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, course_id, kun, question_num, answer, int(bool(is_correct)), datetime.utcnow().isoformat()),
        )
        logger.info("Saved quiz answer for user %s course %s kun=%s question=%s", user_id, course_id, kun, question_num)
        return cur.lastrowid

    def save_lesson(self, user_id: int, kun: int, fan: str, content: str) -> int:
        try:
            cur = self.execute(
                "INSERT INTO lessons (user_id, kun, fan, content) VALUES (?, ?, ?, ?)",
                (user_id, kun, fan, content),
            )
            logger.info("Saved legacy lesson for user %s kun=%s fan=%s", user_id, kun, fan)
            return cur.lastrowid
        except Exception:
            logger.exception("Failed to save legacy lesson for user %s", user_id)
            raise

    def get_user_progress(self, user_id: int) -> Dict[str, Any]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT kun, current_post, lesson_total_posts, fan, daraja FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return {"kun": 1, "current_post": 1, "total_posts": 1, "fan": None, "daraja": None}
        return {
            "kun": row[0] or 1,
            "current_post": row[1] or 1,
            "total_posts": row[2] or 1,
            "fan": row[3],
            "daraja": row[4],
        }

    def close(self) -> None:
        self.connection.close()
