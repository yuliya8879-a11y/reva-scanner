"""Full scan question definitions for personal and business scan types.

Each QuestionDef describes a single question in the questionnaire:
- key: answer storage key used in scan.answers JSONB
- text: Russian-language question text shown to user
- input_type: "keyboard" (inline buttons) or "text" (free-text message)
- options: list of (display_text, callback_value) tuples for keyboard inputs, None for text
- required: True for mandatory questions, False for skippable ones
- max_length: character limit for text inputs, None for no limit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuestionDef:
    """Single question definition for the full scan questionnaire."""

    key: str
    text: str
    input_type: str  # "keyboard" or "text"
    options: Optional[list[tuple[str, str]]] = None
    required: bool = True
    max_length: Optional[int] = None


# ---------------------------------------------------------------------------
# PERSONAL QUESTIONS — 15 total
# ---------------------------------------------------------------------------

PERSONAL_QUESTIONS: list[QuestionDef] = [
    # Q1 (index 0)
    QuestionDef(
        key="birth_date",
        text="Введите вашу дату рождения в формате ДД.ММ.ГГГГ",
        input_type="text",
        options=None,
        required=True,
    ),
    # Q2 (index 1)
    QuestionDef(
        key="name",
        text="Ваше имя / как вас зовут?",
        input_type="text",
        options=None,
        required=True,
    ),
    # Q3 (index 2)
    QuestionDef(
        key="business_area",
        text="Ваша сфера деятельности?",
        input_type="keyboard",
        options=[
            ("Услуги", "services"),
            ("Продукты", "products"),
            ("IT", "it"),
            ("Торговля", "trade"),
            ("Консалтинг", "consulting"),
            ("Другое", "other"),
        ],
        required=True,
    ),
    # Q4 (index 3)
    QuestionDef(
        key="business_age",
        text="Сколько лет вы в бизнесе?",
        input_type="keyboard",
        options=[
            ("< 1", "lt1"),
            ("1-3", "1to3"),
            ("3-7", "3to7"),
            ("7+", "7plus"),
        ],
        required=True,
    ),
    # Q5 (index 4)
    QuestionDef(
        key="role",
        text="Ваша главная роль?",
        input_type="keyboard",
        options=[
            ("Основатель", "founder"),
            ("Директор", "director"),
            ("Партнёр", "partner"),
            ("Менеджер", "manager"),
        ],
        required=True,
    ),
    # Q6 (index 5)
    QuestionDef(
        key="team_size",
        text="Сколько человек в команде?",
        input_type="keyboard",
        options=[
            ("Один", "solo"),
            ("2-5", "2to5"),
            ("6-20", "6to20"),
            ("20+", "20plus"),
        ],
        required=True,
    ),
    # Q7 (index 6)
    QuestionDef(
        key="client_source",
        text="Ваш главный источник клиентов?",
        input_type="keyboard",
        options=[
            ("Сарафан", "referral"),
            ("Реклама", "ads"),
            ("Соцсети", "social"),
            ("Партнёры", "partners"),
            ("Нет системы", "none"),
        ],
        required=True,
    ),
    # Q8 (index 7)
    QuestionDef(
        key="avg_check",
        text="Ваш средний чек?",
        input_type="keyboard",
        options=[
            ("до 5к", "lt5k"),
            ("5-50к", "5to50k"),
            ("50-500к", "50to500k"),
            ("500к+", "500kplus"),
        ],
        required=True,
    ),
    # Q9 (index 8)
    QuestionDef(
        key="main_pain",
        text="Ваша главная боль сейчас?",
        input_type="keyboard",
        options=[
            ("Клиенты", "clients"),
            ("Команда", "team"),
            ("Системы", "systems"),
            ("Деньги", "money"),
            ("Масштаб", "scale"),
        ],
        required=True,
    ),
    # Q10 (index 9)
    QuestionDef(
        key="growth_blocker",
        text="Что мешает расти?",
        input_type="keyboard",
        options=[
            ("Страх", "fear"),
            ("Нет ресурсов", "no_resources"),
            ("Нет стратегии", "no_strategy"),
            ("Внешние факторы", "external"),
        ],
        required=True,
    ),
    # Q11 (index 10)
    QuestionDef(
        key="superpower",
        text="Ваша суперсила в бизнесе?",
        input_type="keyboard",
        options=[
            ("Идеи", "ideas"),
            ("Продажи", "sales"),
            ("Команда", "team"),
            ("Продукт", "product"),
            ("Связи", "connections"),
        ],
        required=True,
    ),
    # Q12 (index 11)
    QuestionDef(
        key="decision_style",
        text="Как принимаете решения?",
        input_type="keyboard",
        options=[
            ("Интуиция", "intuition"),
            ("Данные", "data"),
            ("Советники", "advisors"),
            ("Медленно", "slow"),
        ],
        required=True,
    ),
    # Q13 (index 12)
    QuestionDef(
        key="year_goal",
        text="Ваша цель на год?",
        input_type="keyboard",
        options=[
            ("Удвоить доход", "double_income"),
            ("Выйти на новый рынок", "new_market"),
            ("Систематизировать", "systematize"),
            ("Выйти из операционки", "exit_ops"),
        ],
        required=True,
    ),
    # Q14 (index 13)
    QuestionDef(
        key="current_situation",
        text="Опишите текущую ситуацию (до 1000 символов)",
        input_type="text",
        options=None,
        required=False,
        max_length=1000,
    ),
    # Q15 (index 14)
    QuestionDef(
        key="social_url",
        text="Ссылка на соцсеть или сайт",
        input_type="text",
        options=None,
        required=False,
    ),
]


# ---------------------------------------------------------------------------
# BUSINESS QUESTIONS — 12 total
# Q1-Q10 identical to PERSONAL Q1-Q10
# ---------------------------------------------------------------------------

BUSINESS_QUESTIONS: list[QuestionDef] = [
    # Q1-Q10: reuse personal definitions (same objects, same data)
    *PERSONAL_QUESTIONS[:10],
    # Q11 (index 10)
    QuestionDef(
        key="product_description",
        text="Опишите ваш продукт или услугу — что именно вы продаёте?",
        input_type="text",
        options=None,
        required=False,
        max_length=1000,
    ),
    # Q12 (index 11) — ключевой вопрос для глубины скана
    QuestionDef(
        key="current_situation",
        text=(
            "Опишите текущую ситуацию подробно.\n\n"
            "Что происходит в бизнесе прямо сейчас? Деньги, команда, клиенты, "
            "что тяготит, что не получается изменить?"
        ),
        input_type="text",
        options=None,
        required=False,
        max_length=2000,
    ),
    # Q13 (index 12)
    QuestionDef(
        key="team_conflict",
        text=(
            "Есть ли кто-то в команде или окружении, кто создаёт напряжение, "
            "конфликт или утечку энергии?\n\n"
            "Опишите ситуацию (можно без имён, или с именами — как удобно)."
        ),
        input_type="text",
        options=None,
        required=False,
        max_length=1500,
    ),
    # Q14 (index 13)
    QuestionDef(
        key="scan_request",
        text=(
            "Ваш запрос на сканирование.\n\n"
            "Что хотите понять или получить от этого разбора? "
            "На что направить взгляд сканера?"
        ),
        input_type="text",
        options=None,
        required=False,
        max_length=1000,
    ),
    # Q15 (index 14)
    QuestionDef(
        key="social_url",
        text="Ссылка на сайт или соцсеть (если есть)",
        input_type="text",
        options=None,
        required=False,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_questions_for_type(scan_type: str) -> list[QuestionDef]:
    """Return the question list for the given scan type.

    Args:
        scan_type: "personal" or "business"

    Returns:
        PERSONAL_QUESTIONS or BUSINESS_QUESTIONS

    Raises:
        ValueError: if scan_type is not recognized
    """
    if scan_type == "personal":
        return PERSONAL_QUESTIONS
    if scan_type == "business":
        return BUSINESS_QUESTIONS
    raise ValueError(
        f"Unknown scan_type {scan_type!r}. Expected 'personal' or 'business'."
    )


def get_total_questions(scan_type: str) -> int:
    """Return the total number of questions for the given scan type.

    Args:
        scan_type: "personal" or "business"

    Returns:
        Integer count of questions

    Raises:
        ValueError: if scan_type is not recognized
    """
    return len(get_questions_for_type(scan_type))
