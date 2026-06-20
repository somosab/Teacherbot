import os
import time
import logging
from pathlib import Path
from logger import setup_logger

logger = setup_logger(__name__)


def export_sqlite(db_path: Path, dest_dir: Path) -> Path:
    """Create a timestamped copy of the sqlite DB for backup."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    dest = dest_dir / f"teacherbot-backup-{ts}.db"
    try:
        with open(db_path, 'rb') as src, open(dest, 'wb') as dst:
            dst.write(src.read())
        logger.info("Exported sqlite backup to %s", dest)
        return dest
    except Exception:
        logger.exception("Failed to export sqlite backup")
        raise


def sync_to_supabase(file_path: Path) -> bool:
    """Stub: upload backup file to Supabase (requires SUPABASE_URL and SUPABASE_KEY).

    This function is intentionally simple — in production use supabase-py or signed uploads.
    """
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials missing, skipping cloud sync")
        return False
    logger.info("Would upload %s to Supabase at %s", file_path, SUPABASE_URL)
    # TODO: implement uploads using requests or supabase client
    return True
