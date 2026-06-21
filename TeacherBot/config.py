from pathlib import Path
from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "teacherbot.db")).resolve()
LOG_FILE = Path(os.getenv("LOG_FILE", "teacherbot.log")).resolve()
LESSON_MODEL = os.getenv("LESSON_MODEL", "llama-3.3-70b-versatile").strip()
DEFAULT_LANGUAGE = "uz"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required. Add it to .env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is required. Add it to .env")

POST_COUNT_BY_VAQT = {
    "⚡ 15 daqiqa": 1,
    "📖 30 daqiqa": 2,
    "💪 1 soat": 3,
    "🔥 2 soat+": 4,
    "⚡ 15 минут": 1,
    "📖 30 минут": 2,
    "💪 1 час": 3,
    "🔥 2+ часа": 4,
    "⚡ 15 minutes": 1,
    "📖 30 minutes": 2,
    "💪 1 hour": 3,
    "🔥 2+ hours": 4,
    "⚡ 15 Minuten": 1,
    "📖 30 Minuten": 2,
    "💪 1 Stunde": 3,
    "🔥 2+ Stunden": 4,
    "⚡ 15 minutes": 1,
    "📖 30 minutes": 2,
    "💪 1 heure": 3,
    "🔥 2+ heures": 4,
    "⚡ 15 minutos": 1,
    "📖 30 minutos": 2,
    "💪 1 hora": 3,
    "🔥 2+ horas": 4,
    "⚡ 15 dakika": 1,
    "📖 30 dakika": 2,
    "💪 1 saat": 3,
    "🔥 2+ saat": 4,
    "⚡ 15 دقيقة": 1,
    "📖 30 دقيقة": 2,
    "💪 1 ساعة": 3,
    "🔥 2+ ساعة": 4,
    "⚡ 15分钟": 1,
    "📖 30分钟": 2,
    "💪 1小时": 3,
    "🔥 2+小时": 4,
    "⚡ 15分": 1,
    "📖 30分": 2,
    "💪 1時間": 3,
    "🔥 2+時間": 4,
    "⚡ 15분": 1,
    "📖 30분": 2,
    "💪 1시간": 3,
    "🔥 2+시간": 4,
    "⚡ 15 मिनट": 1,
    "📖 30 मिनट": 2,
    "💪 1 घंटे": 3,
    "🔥 2+ घंटे": 4,
}
