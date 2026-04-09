import re
from datetime import datetime, timedelta

STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "that",
    "this",
    "with",
    "by",
    "as",
    "from",
    "at",
    "и",
    "в",
    "на",
    "с",
    "по",
    "для",
    "это",
    "как",
    "что",
    "или",
    "но",
    "к",
    "из",
    "у",
    "под",
    "над",
    "не",
    "же",
    "так",
    "при",
    "до",
    "после",
    "через",
    "между",
    "если",
    "когда",
    "более",
    "менее",
    "где",
    "бы",
}


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"[.!?\n]+", text)
    return [c.strip() for c in chunks if len(c.strip().split()) >= 4]


def extract_focus_word(sentence: str) -> str | None:
    words = re.findall(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-']+", sentence)
    candidates = [w for w in words if w.lower() not in STOP_WORDS and len(w) > 3]
    if not candidates:
        return None
    return sorted(candidates, key=len, reverse=True)[0]


def generate_cards_from_text(text: str) -> list[tuple[str, str]]:
    cards = []
    for sentence in split_sentences(text):
        answer = extract_focus_word(sentence)
        if not answer:
            continue
        question = re.sub(rf"\b{re.escape(answer)}\b", "____", sentence, count=1)
        if question == sentence:
            continue
        cards.append((f"Fill the missing word: {question}", answer))
    return cards[:20]


def normalize_answer(value: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]", "", value.lower())


def evaluate_answer(expected: str, actual: str) -> bool:
    return normalize_answer(expected) == normalize_answer(actual)


def next_interval_after_answer(current_streak: int, is_correct: bool) -> tuple[int, int]:
    ladder = [1, 3, 7, 14, 30]
    if not is_correct:
        return 0, ladder[0]
    new_streak = current_streak + 1
    idx = min(new_streak - 1, len(ladder) - 1)
    return new_streak, ladder[idx]


def next_review_datetime(interval_days: int) -> datetime:
    return datetime.utcnow() + timedelta(days=interval_days)
