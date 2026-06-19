from typing import Optional
from logger import setup_logger

logger = setup_logger(__name__)


def build_lesson_prompt(fan: str, daraja: str, kun: int, vaqt: str, lang_name: str, extras: Optional[str] = None) -> str:
    """Construct a detailed prompt instructing the model to output the lesson in required sections."""
    difficulty = {
        "🟢 Boshlang'ich": "Beginner: simple words, 1 concept",
        "🟡 O'rta": "Intermediate: 2-3 concepts",
        "🔴 Yuqori": "Advanced: 4-5 concepts, deep dive",
    }.get(darja, "Intermediate")

    template = f"Write a lesson in {lang_name} for the subject '{fan}'.\n"
    template += f"Student level: {daraja} ({difficulty}). Day {kun}. Daily time: {vaqt}.\n"
    if extras:
        template += extras + "\n"

    template += (
        "Output the lesson with the following sections exactly:\n"
        "1) 🎯 LEARNING OBJECTIVES (2-3 bullet points)\n"
        "2) 📚 INTRODUCTION (why it matters)\n"
        "3) 💡 KEY CONCEPTS (3-5 sub-concepts with short explanations)\n"
        "4) 🔍 DETAILED EXAMPLES (3-4 real-world examples with short explanations)\n"
        "5) ✏️ STEP-BY-STEP PRACTICE (5 steps, easy→hard)\n"
        "6) 🧠 CONCEPT CHECK (3-5 multiple-choice questions A/B/C/D)\n"
        "7) 📝 HOMEWORK (one real assignment)\n"
        "8) 🔮 NEXT LESSON PREVIEW\n"
        "9) 💬 COMMON MISTAKES\n"
        "10) 🔗 RESOURCES\n"
    )

    template += (
        "Make sections clearly separated and labeled. Use short paragraphs and examples."
    )

    return template


def generate_lesson(groq_client, fan: str, daraja: str, kun: int, vaqt: str, lang: str, lang_name: str, extras: Optional[str] = None) -> str:
    prompt = build_lesson_prompt(fan, daraja, kun, vaqt, lang_name, extras=extras)
    try:
        response = groq_client.chat.completions.create(
            model=None if not hasattr(groq_client, 'default_model') else groq_client.default_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception:
        logger.exception("Lesson generation failed for %s day %s", fan, kun)
        # Fallback: small scaffolded lesson
        fallback = (
            "🎯 LEARNING OBJECTIVES:\n- Understand core idea\n- Practice basic examples\n"
            "📚 INTRODUCTION:\nShort intro.\n"
            "💡 KEY CONCEPTS:\n1) Concept A - short\n"
            "🔍 DETAILED EXAMPLES:\nExample 1: ...\n"
            "✏️ STEP-BY-STEP PRACTICE:\n1) Try X\n"
            "🧠 CONCEPT CHECK:\n1) Q: ... A) ... B) ... C) ... D) ...\n"
            "📝 HOMEWORK:\nDo a short task.\n"
            "🔮 NEXT LESSON PREVIEW:\nNext we will...\n"
            "💬 COMMON MISTAKES:\n- Mixing X and Y\n"
            "🔗 RESOURCES:\n- Read more"
        )
        return fallback
