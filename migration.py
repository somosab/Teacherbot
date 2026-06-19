"""Database migration helper.

Run this script to ensure new tables exist and perform light migrations.
"""
from database import Database
from config import DATABASE_PATH
from logger import setup_logger

logger = setup_logger(__name__)


def migrate():
    db = Database(DATABASE_PATH)
    # Ensure legacy columns exist in users table
    cursor = db.connection.cursor()

    def ensure_column(table: str, column: str, definition: str):
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cursor.fetchall()]
        if column not in cols:
            logger.info("Adding column %s to %s", column, table)
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    try:
        ensure_column('users', 'fan', 'TEXT')
        ensure_column('users', 'daraja', 'TEXT')
        ensure_column('users', 'maqsad', 'TEXT')
        ensure_column('users', 'vaqt', 'TEXT')
        ensure_column('users', 'kun', 'INTEGER DEFAULT 1')
        ensure_column('users', 'current_post', 'INTEGER DEFAULT 1')
        ensure_column('users', 'lesson_total_posts', 'INTEGER DEFAULT 1')
        ensure_column('users', 'next_day_unlock', 'TEXT')
        ensure_column('users', 'state', 'TEXT')
        ensure_column('users', 'last_lesson', 'TEXT')
        ensure_column('users', 'last_active', 'TEXT')

        # Ensure `lessons` and `quiz_answers` tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lessons'")
        if not cursor.fetchone():
            logger.info("Creating lessons table")
            cursor.execute(
                """
                CREATE TABLE lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    kun INTEGER,
                    fan TEXT,
                    content TEXT,
                    saved_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quiz_answers'")
        if not cursor.fetchone():
            logger.info("Creating quiz_answers table")
            cursor.execute(
                """
                CREATE TABLE quiz_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    kun INTEGER,
                    question_num INTEGER,
                    answer TEXT,
                    is_correct INTEGER,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        db.connection.commit()
        logger.info("Migration completed (ensured legacy columns and tables)")
    except Exception:
        logger.exception("Migration failed")
    finally:
        db.close()


if __name__ == '__main__':
    migrate()
