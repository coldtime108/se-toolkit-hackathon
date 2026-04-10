import json
import os
import re
from datetime import datetime, timedelta
from urllib import error as urlerror
from urllib import request as urlrequest

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


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_focus_word(sentence: str) -> str | None:
    words = re.findall(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-']+", sentence)
    candidates = [w for w in words if w.lower() not in STOP_WORDS and len(w) > 3]
    if not candidates:
        return None
    return sorted(candidates, key=len, reverse=True)[0]


def build_question_from_sentence(sentence: str) -> tuple[str, str] | None:
    cleaned = normalize_text(sentence).rstrip(".")
    if not cleaned:
        return None

    focus = extract_focus_word(cleaned)
    if not focus:
        return None

    lowered = cleaned.lower()
    if " should " in lowered:
        prefix = cleaned.split(" should ", 1)[0].strip()
        if len(prefix.split()) >= 2:
            question = f"What should {prefix} do?"
        else:
            question = f"What should you remember about {focus.lower()}?"
    elif any(word in lowered for word in (" improves ", " increases ", " reduces ", " helps ")):
        question = f"How does {focus.lower()} affect the topic?"
    elif " because " in lowered or " by " in lowered:
        question = f"Why is {focus.lower()} important?"
    else:
        question = f"What does the note say about {focus.lower()}?"

    answer = cleaned[0].upper() + cleaned[1:]
    if not question.endswith("?"):
        question += "?"
    return question, answer


def generate_cards_from_text(text: str) -> list[tuple[str, str]]:
    cards = []
    for sentence in split_sentences(text):
        card = build_question_from_sentence(sentence)
        if not card:
            continue
        question, answer = card
        cards.append((question, answer))
    return cards[:20]


def is_good_generated_card(question: str, answer: str) -> bool:
    normalized_question = normalize_text(question).lower()
    normalized_answer = normalize_text(answer)
    if not normalized_question or not normalized_answer:
        return False
    if "____" in normalized_question:
        return False
    if any(token in normalized_question for token in ("fill the missing word", "blank", "cloze", "missing word")):
        return False
    if len(normalized_question.split()) < 3:
        return False
    if not normalized_question.endswith("?"):
        return False
    return True


def _extract_json_object(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if "{" in cleaned:
            cleaned = cleaned[cleaned.find("{") :]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def generate_cards_from_llm(text: str, limit: int) -> list[tuple[str, str]]:
    base_url = os.environ.get("LLM_API_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    model = os.environ.get("LLM_API_MODEL", "qwen2.5:3b-instruct")
    api_key = os.environ.get("LLM_API_KEY", "").strip()

    prompt = (
        "Create study cards from the note below. "
        "The questions must be genuine study questions, not fill-in-the-blank prompts. "
        "Prefer why, how, what, compare, explain, or define style questions. "
        f"Return a strict JSON object with a single key named cards, containing at most {limit} items. "
        "Each item must have question and answer keys with concise text. "
        "Do not add markdown, code fences, or commentary. "
        "Every question must end with a question mark.\n\n"
        f"NOTE:\n{text.strip()}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You generate study flashcards as strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urlrequest.Request(f"{base_url}/chat/completions", data=body, headers=headers, method="POST")

    try:
        with urlrequest.urlopen(request, timeout=12) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (OSError, urlerror.URLError, ValueError):
        return []

    try:
        content = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return []

    parsed = _extract_json_object(content)
    if not parsed:
        return []

    raw_cards = parsed.get("cards", [])
    cards: list[tuple[str, str]] = []
    for item in raw_cards:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not is_good_generated_card(question, answer):
            continue
        cards.append((normalize_text(question)[:500], normalize_text(answer)[:250]))
        if len(cards) >= limit:
            break
    return cards


def generate_quiz_cards(text: str, limit: int) -> tuple[list[tuple[str, str]], str]:
    llm_cards = generate_cards_from_llm(text, limit)
    if llm_cards:
        return llm_cards[:limit], "local Qwen"

    heuristic_cards = generate_cards_from_text(text)
    if heuristic_cards:
        return heuristic_cards[:limit], "built-in fallback"

    return [], "none"


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
