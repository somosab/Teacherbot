from pathlib import Path
from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent
DOTENV_PATH = ROOT_DIR / ".env"
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH, override=False)

def get_env_value(name: str, default: str = "", required: bool = False) -> str:
    value = os.getenv(name, default).strip()
    if required and not value:
        raise ValueError(f"{name} is required. Set it in the environment or add it to .env")
    return value

BOT_TOKEN = get_env_value("BOT_TOKEN", required=True)
GROQ_API_KEY = get_env_value("GROQ_API_KEY", required=True)
DATABASE_PATH = Path(get_env_value("DATABASE_PATH", "teacherbot.db")).resolve()
LOG_FILE = Path(get_env_value("LOG_FILE", "teacherbot.log")).resolve()
LESSON_MODEL = get_env_value("LESSON_MODEL", "llama-3.3-70b-versatile")
DEFAULT_LANGUAGE = "uz"

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
