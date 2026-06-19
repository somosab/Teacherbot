import atexit
from datetime import datetime, timedelta, timezone
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, GROQ_API_KEY, DATABASE_PATH, LESSON_MODEL, DEFAULT_LANGUAGE
from database import Database
from logger import setup_logger
from languages import LANGUAGES, get_text, get_lang_name, get_fields, get_vaqt_options, get_levels, get_subfields
from session_manager import get_resume_message, resume_available, save_session_state, clear_session
from dashboard import build_course_dashboard, course_menu_markup, build_statistics_text
from lesson_generator import generate_lesson
from backup_manager import export_sqlite, sync_to_supabase

logger = setup_logger(__name__)
db = Database(DATABASE_PATH)
groq_client = Groq(api_key=GROQ_API_KEY)

USER_DB_FIELDS = {
    "lang",
    "soha",
    "category",
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
}

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
    "💪 1 घंटा": 3,
    "🔥 2+ घंटे": 4,
}


def parse_datetime(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return value


def persist_user_state(user_id: int, user_data: dict) -> None:
    values = {key: user_data.get(key) for key in USER_DB_FIELDS if user_data.get(key) is not None}
    if values:
        db.upsert_user(user_id, **values)


def load_course_context(course, context) -> None:
    if not course:
        return
    context.user_data["course_id"] = course.get("course_id")
    context.user_data["fan"] = course.get("fan")
    context.user_data["daraja"] = course.get("daraja")
    context.user_data["maqsad"] = course.get("maqsad")
    context.user_data["vaqt"] = course.get("vaqt")
    context.user_data["kun"] = int(course.get("current_kun", 1)) if course.get("current_kun") is not None else 1
    context.user_data["current_post"] = int(course.get("current_post", 1)) if course.get("current_post") is not None else 1
    context.user_data["lesson_total_posts"] = int(course.get("total_posts_per_day", POST_COUNT_BY_VAQT.get(course.get("vaqt"), 1)))
    context.user_data.pop("next_day_unlock", None)


def parse_course_action(text: str):
    for prefix, action in [
        ("📖 CONTINUE ", "continue"),
        ("⏸️ PAUSE ", "pause"),
        ("▶️ RESUME ", "resume"),
        ("🗑️ DELETE ", "delete"),
    ]:
        if text.startswith(prefix):
            digits = "".join(ch for ch in text if ch.isdigit())
            try:
                return action, int(digits)
            except ValueError:
                return None, None
    return None, None


def get_current_course_id(update, context):
    course_id = context.user_data.get("course_id")
    if course_id:
        try:
            return int(course_id)
        except (TypeError, ValueError):
            pass
    active_course = db.get_active_course(update.effective_user.id)
    return active_course.get("course_id") if active_course else None


def load_user_state(user_id: int, context) -> None:
    user_record = db.get_user(user_id)
    if not user_record:
        context.user_data.clear()
        context.user_data["lang"] = DEFAULT_LANGUAGE
        return
    for key, value in user_record.items():
        if key in USER_DB_FIELDS and value is not None:
            context.user_data[key] = value


def is_next_day_unlocked(context):
    unlock_at = parse_datetime(context.user_data.get("next_day_unlock"))
    if unlock_at is None:
        return True
    return datetime.now(timezone.utc) >= unlock_at


def t(context, key, **kwargs):
    lang = context.user_data.get("lang", DEFAULT_LANGUAGE)
    return get_text(lang, key, **kwargs)


def lesson_keyboard(context):
    lang = context.user_data.get("lang", DEFAULT_LANGUAGE)
    current_post = int(context.user_data.get("current_post", 1))
    total_posts = int(context.user_data.get("lesson_total_posts", 1))
    next_day_unlock = context.user_data.get("next_day_unlock")
    buttons = []

    if current_post < total_posts:
        buttons.append([get_text(lang, "next_post"), get_text(lang, "understood")])
    elif current_post == total_posts and next_day_unlock is None:
        buttons.append([get_text(lang, "understood"), get_text(lang, "not_understood")])
    else:
        if is_next_day_unlocked(context):
            buttons.append([get_text(lang, "next_lesson", kun=context.user_data.get("kun", 2))])
        else:
            buttons.append([get_text(lang, "next_day_locked")])

    if context.user_data.get("course_id"):
        buttons.append(["⏸️ PAUSE COURSE", "⏹️ EXIT COURSE"])

    buttons.append([get_text(lang, "ask"), get_text(lang, "home")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def initialize_user(update, context):
    user_id = update.effective_user.id
    if not context.user_data.get("user_loaded"):
        load_user_state(user_id, context)
        context.user_data["user_loaded"] = True


async def send_lesson(update, context, understood=True):
    fan = context.user_data.get("fan", "Python")
    daraja = context.user_data.get("daraja", "🟢 Boshlang'ich")
    maqsad = context.user_data.get("maqsad", "📚 Bilim olish")
    vaqt = context.user_data.get("vaqt", "📖 30 daqiqa")
    lang = context.user_data.get("lang", DEFAULT_LANGUAGE)
    kun = int(context.user_data.get("kun", 1))
    previous = context.user_data.get("last_lesson")

    current_post = int(context.user_data.get("current_post", 1))
    total_posts = int(context.user_data.get("lesson_total_posts", 1))
    extra = (
        f"\nUser did NOT understand the previous lesson. Use simpler words, more analogies and examples.\nPrevious: {previous[:400]}"
        if (not understood and previous)
        else f"\nThis is day {kun}."
    )
    lang_name = get_lang_name(lang)

    template = get_text(
        lang,
        "lesson_template",
        fan=fan,
        daraja=daraja,
        maqsad=maqsad,
        vaqt=vaqt,
        extra=extra,
        kun=kun,
        lang_name=lang_name,
    )
    if total_posts > 1:
        template += t(context, "post_note", current_post=current_post, total_posts=total_posts)

    await update.message.reply_text(t(context, "loading"))
    try:
        response = groq_client.chat.completions.create(
            model=LESSON_MODEL,
            messages=[{"role": "user", "content": template}],
        )
        ai_text = response.choices[0].message.content
    except Exception:
        logger.exception("Failed to generate lesson for user %s", update.effective_user.id)
        await update.message.reply_text(
            "⚠️ Something went wrong while preparing your lesson. Please try again later."
        )
        return

    context.user_data["last_lesson"] = ai_text
    persist_user_state(update.effective_user.id, context.user_data)

    course_id = context.user_data.get("course_id")
    if course_id:
        try:
            db.save_course_lesson(course_id, kun, current_post, ai_text)
        except Exception:
            logger.exception("Failed to save course lesson for user %s course %s", update.effective_user.id, course_id)

    try:
        db.save_lesson(update.effective_user.id, kun, fan, ai_text)
    except Exception:
        logger.exception("Failed to persist lesson for user %s", update.effective_user.id)

    await update.message.reply_text(ai_text, reply_markup=lesson_keyboard(context))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info("Starting session for user %s", user_id)
    # Ensure user exists and load minimal defaults
    db.ensure_user(user_id)
    context.user_data.clear()
    context.user_data["user_loaded"] = True

    # If user has an active course, show dashboard
    active = db.get_active_course(user_id)
    if active:
        courses = db.get_all_user_courses(user_id)
        card = build_course_dashboard(user_id, db)
        markup = course_menu_markup(courses)
        await update.message.reply_text(card, reply_markup=markup)
        return

    # No active course — ask language and start new flow
    context.user_data["lang"] = DEFAULT_LANGUAGE
    langs = list(LANGUAGES.keys())
    keyboard = [langs[i : i + 2] for i in range(0, len(langs), 2)]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Welcome! / Xush kelibsiz!\n\n🌍 Choose your language / Tilni tanlang:",
        reply_markup=markup,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.effective_user:
            return

        initialize_user(update, context)
        text = update.message.text
        lang = context.user_data.get("lang", DEFAULT_LANGUAGE)

        if context.user_data.get("awaiting_exit_confirmation"):
            if text == "Ha, chiqaman":
                course_id = context.user_data.get("exit_course_id") or get_current_course_id(update, context)
                if course_id:
                    try:
                        db.delete_course(update.effective_user.id, int(course_id))
                    except Exception:
                        logger.exception("Failed to abandon course %s for user %s", course_id, update.effective_user.id)
                context.user_data.pop("awaiting_exit_confirmation", None)
                context.user_data.pop("exit_course_id", None)
                await update.message.reply_text("Kurs bekor qilindi. /start ni bosing")
                await start(update, context)
                return

            if text == "Yo'q, davom etaman":
                context.user_data.pop("awaiting_exit_confirmation", None)
                context.user_data.pop("exit_course_id", None)
                await update.message.reply_text("Davom etamiz.", reply_markup=lesson_keyboard(context))
                return

            await update.message.reply_text("Iltimos, tanlang: Ha, chiqaman yoki Yo'q, davom etaman.")
            return

        if context.user_data.get("awaiting_resume_choice"):
            if text == "YES":
                session = context.user_data.get("resume_session")
                course = db.get_course(session.get("course_id")) if session else None
                if course:
                    load_course_context(course, context)
                    await send_lesson(update, context, understood=True)
                else:
                    await update.message.reply_text("Qayta boshlash uchun kurs topilmadi. Iltimos /start ni bosing.")
                context.user_data.pop("awaiting_resume_choice", None)
                context.user_data.pop("resume_session", None)
                return

            if text == "START OVER":
                session = context.user_data.get("resume_session")
                course = db.get_course(session.get("course_id")) if session else None
                if course:
                    load_course_context(course, context)
                    context.user_data["kun"] = 1
                    context.user_data["current_post"] = 1
                    await send_lesson(update, context, understood=True)
                else:
                    await update.message.reply_text("Kurs topilmadi. Iltimos /start ni bosing.")
                context.user_data.pop("awaiting_resume_choice", None)
                context.user_data.pop("resume_session", None)
                return

            if text == "⚙️ SETTINGS":
                context.user_data.pop("awaiting_resume_choice", None)
                await update.message.reply_text("⚙️ Sozlamalar hali tayyor emas. /start ni bosing yoki davom eting.")
                return

            if text == "📊 STATISTICS":
                context.user_data.pop("awaiting_resume_choice", None)
                stats_text = build_statistics_text(update.effective_user.id, db)
                await update.message.reply_text(stats_text)
                return

            await update.message.reply_text("Iltimos, tanlang: YES, START OVER, ⚙️ SETTINGS yoki 📊 STATISTICS.")
            return

        course_action, selected_course_id = parse_course_action(text)
        if course_action:
            if course_action in ("continue", "resume"):
                course = db.resume_course(update.effective_user.id, selected_course_id)
                if not course:
                    await update.message.reply_text("Kurs topilmadi. Iltimos /start ni bosing.")
                    return
                load_course_context(course, context)
                await send_lesson(update, context, understood=True)
                return

            if course_action == "pause":
                try:
                    db.pause_course(update.effective_user.id, selected_course_id)
                except Exception:
                    logger.exception("Failed to pause course %s for user %s", selected_course_id, update.effective_user.id)
                await update.message.reply_text("Kurs pauzalandi. Qayta boshlash uchun /start ni bosing")
                await start(update, context)
                return

            if course_action == "delete":
                try:
                    db.delete_course(update.effective_user.id, selected_course_id)
                except Exception:
                    logger.exception("Failed to delete course %s for user %s", selected_course_id, update.effective_user.id)
                await update.message.reply_text("Kurs bekor qilindi. /start ni bosing")
                await start(update, context)
                return

        if text == "📖 CONTINUE LESSON":
            session = db.get_session(update.effective_user.id)
            if not session:
                await update.message.reply_text("No active session found. Start a new course from the menu.")
                return
            course = db.get_course(session.get("course_id"))
            msg = f"Welcome back! You were on Day {session.get('last_accessed_kun')} | Post {session.get('last_accessed_post')} of {course.get('total_days') if course else '?'}"
            keyboard = [["YES", "START OVER"], ["⚙️ SETTINGS", "📊 STATISTICS"]]
            await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            context.user_data['awaiting_resume_choice'] = True
            context.user_data['resume_session'] = session
            return

        if text == "⏸️ PAUSE COURSE":
            course_id = get_current_course_id(update, context)
            if not course_id:
                await update.message.reply_text("Kurs topilmadi. /start ni bosing va qayta boshlang.")
                return
            current_kun = int(context.user_data.get("kun", 1))
            current_post = int(context.user_data.get("current_post", 1))
            try:
                db.update_course_progress(course_id, current_kun, current_post, understood=True)
                db.pause_course(update.effective_user.id, course_id)
            except Exception:
                logger.exception("Failed to pause course %s for user %s", course_id, update.effective_user.id)
                await update.message.reply_text("⚠️ Kursni pauzalashda xatolik yuz berdi.")
                return
            await update.message.reply_text("Kurs pauzalandi. Qayta boshlash uchun /start ni bosing")
            await start(update, context)
            return

        if text == "⏹️ EXIT COURSE":
            course_id = get_current_course_id(update, context)
            if not course_id:
                await update.message.reply_text("Kurs topilmadi. /start ni bosing va qayta boshlang.")
                return
            context.user_data["awaiting_exit_confirmation"] = True
            context.user_data["exit_course_id"] = course_id
            keyboard = ReplyKeyboardMarkup(
                [["Ha, chiqaman"], ["Yo'q, davom etaman"]],
                resize_keyboard=True,
            )
            await update.message.reply_text(
                "Rostancha chiqmoqchimisiz? Davom ettira olasiz keyin.",
                reply_markup=keyboard,
            )
            return

        if text == "➕ START NEW COURSE":
            context.user_data.clear()
            context.user_data["user_loaded"] = True
            context.user_data["lang"] = DEFAULT_LANGUAGE
            langs = list(LANGUAGES.keys())
            keyboard = [langs[i : i + 2] for i in range(0, len(langs), 2)]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "👋 Ready for a new course! Choose your language:",
                reply_markup=markup,
            )
            return

        if text == "📊 STATISTICS":
            stats_text = build_statistics_text(update.effective_user.id, db)
            await update.message.reply_text(stats_text)
            return

        if text == "⚙️ SETTINGS":
            await update.message.reply_text("⚙️ Sozlamalar hali tayyor emas. /start ni bosing yoki davom eting.")
            return

        if text == "🎯 MY COURSES":
            courses = db.list_user_courses(update.effective_user.id)
            if not courses:
                await update.message.reply_text("You have no courses. Start a new course from the menu.")
                return
            lines = []
            for c in courses:
                lines.append(f"{c.get('course_id')}: {c.get('fan')} — {c.get('status')} — {c.get('current_kun')}/{c.get('total_days')}")
            await update.message.reply_text("\n".join(lines))
            return

        fields = get_fields(lang)
        all_subjects = [subj for field in fields.values() for row in field for subj in row]
        for subject in list(all_subjects):
            subfields = get_subfields(lang, subject)
            if subfields:
                all_subjects.extend([subj for row in subfields for subj in row])
        all_sohas = list(fields.keys())

        if text in LANGUAGES:
            context.user_data["lang"] = LANGUAGES[text]
            lang = LANGUAGES[text]
            fields = get_fields(lang)
            all_sohas = list(fields.keys())
            keyboard = [all_sohas[i : i + 2] for i in range(0, len(all_sohas), 2)]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(t(context, "soha"), reply_markup=markup)

        elif text in all_sohas:
            context.user_data["soha"] = text
            markup = ReplyKeyboardMarkup(fields[text], resize_keyboard=True)
            await update.message.reply_text(t(context, "fan"), reply_markup=markup)

        elif text in all_subjects:
            subfields = get_subfields(lang, text)
            if subfields:
                context.user_data["soha"] = text
                context.user_data["category"] = text
                markup = ReplyKeyboardMarkup(subfields + [[get_text(lang, "home")]], resize_keyboard=True)
                await update.message.reply_text(t(context, "choose_topic"), reply_markup=markup)
            else:
                context.user_data["fan"] = text
                context.user_data.pop("daraja", None)
                context.user_data.pop("maqsad", None)
                context.user_data.pop("vaqt", None)
                daraja_unknown = get_text(lang, "daraja_unknown")
                daraja_buttons = get_levels(lang)
                keyboard = [[daraja_buttons[0]], [daraja_buttons[1]], [daraja_buttons[2]], [daraja_unknown]]
                markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(f"📚 {text}\n\n" + t(context, "daraja"), reply_markup=markup)

        elif text == get_text(lang, "daraja_unknown"):
            fan = context.user_data.get("fan", "")
            test_prompt = get_text(lang, "test_prompt", fan=fan, lang_name=get_lang_name(lang))
            await update.message.reply_text(t(context, "test_loading"))
            try:
                response = groq_client.chat.completions.create(
                    model=LESSON_MODEL,
                    messages=[{"role": "user", "content": test_prompt}],
                )
                await update.message.reply_text(response.choices[0].message.content)
            except Exception:
                logger.exception("Failed to generate test prompt for %s", update.effective_user.id)
                await update.message.reply_text(
                    "⚠️ Something went wrong while preparing your test. Please try again later."
                )
                return
            daraja_buttons = get_levels(lang)
            keyboard = [daraja_buttons]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(t(context, "test_result"), reply_markup=markup)

        elif text in get_levels(lang):
            context.user_data["daraja"] = text
            keyboard = [[t(context, "pro")], [t(context, "job")], [t(context, "learn")], [t(context, "project")]]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(t(context, "maqsad"), reply_markup=markup)

        elif context.user_data.get("daraja") and not context.user_data.get("maqsad"):
            context.user_data["maqsad"] = text
            vaqt_options = get_vaqt_options(lang)
            keyboard = [[opt] for opt in vaqt_options]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(t(context, "vaqt"), reply_markup=markup)

        elif text in get_vaqt_options(lang):
            context.user_data["vaqt"] = text
            context.user_data["kun"] = 1
            context.user_data["lesson_total_posts"] = POST_COUNT_BY_VAQT.get(text, 1)
            context.user_data["current_post"] = 1
            context.user_data.pop("next_day_unlock", None)
            course_id = db.create_course(
                update.effective_user.id,
                context.user_data.get("fan", "Python"),
                context.user_data.get("daraja", "🟢 Boshlang'ich"),
                context.user_data.get("maqsad", "📚 Bilim olish"),
                text,
            )
            context.user_data["course_id"] = course_id
            await send_lesson(update, context, understood=True)

        elif text == get_text(lang, "next_post"):
            current_post = int(context.user_data.get("current_post", 1))
            total_posts = int(context.user_data.get("lesson_total_posts", 1))
            if current_post < total_posts:
                context.user_data["current_post"] = current_post + 1
                await send_lesson(update, context, understood=True)
            else:
                await update.message.reply_text(t(context, "next_day_locked"), reply_markup=lesson_keyboard(context))

        elif text == get_text(lang, "next_day_locked"):
            await update.message.reply_text(t(context, "next_day_locked"), reply_markup=lesson_keyboard(context))

        elif text == get_text(lang, "understood"):
            current_post = int(context.user_data.get("current_post", 1))
            total_posts = int(context.user_data.get("lesson_total_posts", 1))
            course_id = context.user_data.get("course_id")
            if current_post < total_posts:
                if course_id:
                    try:
                        db.update_course_progress(course_id, int(context.user_data.get("kun", 1)), current_post, understood=True)
                    except Exception:
                        logger.exception("Failed to update course progress for user %s course %s", update.effective_user.id, course_id)
                await update.message.reply_text(t(context, "post_understood"), reply_markup=lesson_keyboard(context))
            else:
                kun = int(context.user_data.get("kun", 1))
                context.user_data["kun"] = kun + 1
                context.user_data["next_day_unlock"] = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
                if course_id:
                    try:
                        db.update_course_progress(course_id, kun, current_post, understood=True)
                    except Exception:
                        logger.exception("Failed to update course progress for user %s course %s", update.effective_user.id, course_id)
                else:
                    db.increment_completed_lessons(update.effective_user.id)
                next_text = get_text(lang, "next_day_locked")
                keyboard = [[next_text], [get_text(lang, "home")]]
                markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(get_text(lang, "lesson_done", kun=kun), reply_markup=markup)

        elif text == get_text(lang, "not_understood"):
            await send_lesson(update, context, understood=False)

        elif text == get_text(lang, "next_lesson", kun=context.user_data.get("kun", 2)):
            await send_lesson(update, context, understood=True)

        elif text == get_text(lang, "ask"):
            context.user_data["state"] = "asking"
            await update.message.reply_text(t(context, "ask_prompt"))

        elif text == get_text(lang, "home"):
            await start(update, context)

        elif context.user_data.get("state") == "asking":
            fan = context.user_data.get("fan", "")
            answer_prompt = get_text(
                lang,
                "answer_prompt",
                fan=fan,
                lang_name=get_lang_name(lang),
                question=text,
            )
            try:
                response = groq_client.chat.completions.create(
                    model=LESSON_MODEL,
                    messages=[{"role": "user", "content": answer_prompt}],
                )
                await update.message.reply_text(response.choices[0].message.content, reply_markup=lesson_keyboard(context))
            except Exception:
                logger.exception("Failed to answer question for %s", update.effective_user.id)
                await update.message.reply_text(
                    "⚠️ I couldn't generate an answer right now. Please try again later."
                )
            finally:
                context.user_data["state"] = None

        else:
            logger.info("Unhandled text from user %s: %s", update.effective_user.id, text)
            await update.message.reply_text(
                "⚠️ I didn't understand that. Please choose one of the menu options or type /start to restart."
            )

        persist_user_state(update.effective_user.id, context.user_data)
    except Exception:
        logger.exception("Error handling update for user %s", update.effective_user.id if update.effective_user else "unknown")
        await update.message.reply_text(
            "⚠️ Unexpected error occurred. Please try again later."
        )


def on_shutdown():
    logger.info("Shutting down and closing database connection")
    db.close()


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Teacher Bot is running")
    app.run_polling()


if __name__ == "__main__":
    atexit.register(on_shutdown)
    main()
