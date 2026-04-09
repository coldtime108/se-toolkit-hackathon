import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .db import Base, engine, get_db
from .models import Card, InsightEntry, Note, QuizResponse, QuizSession, ReviewState, Topic, User
from .schemas import (
    AnswerRequest,
    AuthLogin,
    AuthRegister,
    CardCreate,
    CardUpdate,
    InsightEntryCreate,
    InsightEntryUpdate,
    NoteCreate,
    QuizGenerationPreviewRequest,
    QuizGenerationSaveRequest,
    TopicCreate,
    TopicUpdate,
)
from .services import evaluate_answer, generate_cards_from_text, next_interval_after_answer, next_review_datetime

Base.metadata.create_all(bind=engine)


def ensure_sqlite_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    column_map = {
        "topics": {"user_id": "INTEGER"},
        "quiz_sessions": {"user_id": "INTEGER"},
        "quiz_responses": {"user_id": "INTEGER"},
    }

    with engine.begin() as conn:
        for table_name, columns in column_map.items():
            if table_name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspect(conn).get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


ensure_sqlite_columns()

app = FastAPI(title="NeuroSprint Study")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("NEUROSPRINT_SECRET_KEY", "neurosprint-study-secret"))

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    actual_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), actual_salt, 120_000)
    return actual_salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    _, computed_hash = hash_password(password, bytes.fromhex(salt_hex))
    return computed_hash == expected_hash


def get_session_user_id(request: Request) -> int | None:
    return request.session.get("user_id")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = get_session_user_id(request)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def owned_topic_or_404(topic_id: int, user: User, db: Session) -> Topic:
    topic = db.query(Topic).filter(Topic.id == topic_id, Topic.user_id == user.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def owned_card_or_404(card_id: int, user: User, db: Session) -> Card:
    card = (
        db.query(Card)
        .join(Topic, Card.topic_id == Topic.id)
        .filter(Card.id == card_id, Topic.user_id == user.id)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def owned_session_or_404(session_id: int, user: User, db: Session) -> QuizSession:
    session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def owned_insight_or_404(entry_id: int, user: User, db: Session) -> InsightEntry:
    entry = db.query(InsightEntry).filter(InsightEntry.id == entry_id, InsightEntry.user_id == user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/neurosprint")


@app.get("/neurosprint", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/auth/me")
def auth_me(current_user: User | None = Depends(get_current_user)):
    if not current_user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": {"id": current_user.id, "username": current_user.username}}


@app.post("/api/auth/register")
def register(payload: AuthRegister, request: Request, db: Session = Depends(get_db)):
    username = payload.username.strip()
    password = payload.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password must not be empty")

    existing = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    salt_hex, password_hash = hash_password(password)
    user = User(username=username, password_salt=salt_hex, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return {"id": user.id, "username": user.username}


@app.post("/api/auth/login")
def login(payload: AuthLogin, request: Request, db: Session = Depends(get_db)):
    username = payload.username.strip()
    password = payload.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password must not be empty")

    user = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    if not user or not verify_password(password, user.password_salt, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    request.session["user_id"] = user.id
    return {"id": user.id, "username": user.username}


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"status": "ok"}


@app.get("/api/auth/logout")
def logout_via_get(request: Request):
    request.session.clear()
    return {"status": "ok"}


@app.post("/api/topics")
def create_topic(payload: TopicCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    topic = Topic(user_id=current_user.id, title=payload.title.strip())
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "title": topic.title}


@app.get("/api/topics")
def list_topics(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    topics = db.query(Topic).filter(Topic.user_id == current_user.id).order_by(Topic.created_at.desc()).all()
    return [
        {
            "id": topic.id,
            "title": topic.title,
            "cards_count": db.query(func.count(Card.id)).filter(Card.topic_id == topic.id).scalar() or 0,
        }
        for topic in topics
    ]


@app.patch("/api/topics/{topic_id}")
def update_topic(topic_id: int, payload: TopicUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    topic = owned_topic_or_404(topic_id, current_user, db)
    topic.title = payload.title.strip()
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "title": topic.title}


@app.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    topic = owned_topic_or_404(topic_id, current_user, db)

    card_ids = [row[0] for row in db.query(Card.id).filter(Card.topic_id == topic_id).all()]
    if card_ids:
        db.query(ReviewState).filter(ReviewState.card_id.in_(card_ids)).delete(synchronize_session=False)
        db.query(QuizResponse).filter(QuizResponse.card_id.in_(card_ids)).delete(synchronize_session=False)
        db.query(Card).filter(Card.id.in_(card_ids)).delete(synchronize_session=False)

    db.query(Note).filter(Note.topic_id == topic_id).delete(synchronize_session=False)
    db.delete(topic)
    db.commit()
    return {"status": "ok"}


@app.post("/api/topics/{topic_id}/notes")
def add_note(topic_id: int, payload: NoteCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    owned_topic_or_404(topic_id, current_user, db)
    note = Note(topic_id=topic_id, content=payload.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"note_id": note.id, "cards_created": 0}


@app.post("/api/quiz-generator/preview")
def quiz_generator_preview(
    payload: QuizGenerationPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    _ = db, current_user
    pairs = generate_cards_from_text(payload.text)
    limited_pairs = pairs[: payload.limit]
    cards = [{"question": question.strip(), "answer": answer.strip()} for question, answer in limited_pairs]

    if not cards:
        raise HTTPException(
            status_code=400,
            detail="Could not generate quiz cards from this text. Try a longer and more detailed note.",
        )

    return {
        "cards": cards,
        "count": len(cards),
        "message": "Draft cards generated. Review and save them to a topic.",
    }


@app.post("/api/quiz-generator/save")
def quiz_generator_save(
    payload: QuizGenerationSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    topic = owned_topic_or_404(payload.topic_id, current_user, db)

    created_ids: list[int] = []
    for item in payload.cards:
        question = item.question.strip()
        answer = item.answer.strip()
        if not question or not answer:
            continue

        card = Card(topic_id=topic.id, question=question, answer=answer)
        db.add(card)
        db.flush()

        state = ReviewState(
            card_id=card.id,
            streak=0,
            interval_days=1,
            next_review_at=datetime.utcnow(),
        )
        db.add(state)
        created_ids.append(card.id)

    if not created_ids:
        raise HTTPException(status_code=400, detail="No valid cards to save.")

    db.commit()
    return {
        "status": "ok",
        "topic_id": topic.id,
        "topic_title": topic.title,
        "saved_count": len(created_ids),
        "card_ids": created_ids,
    }


@app.post("/api/topics/{topic_id}/cards")
def create_card(topic_id: int, payload: CardCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    owned_topic_or_404(topic_id, current_user, db)
    card = Card(topic_id=topic_id, question=payload.question.strip(), answer=payload.answer.strip())
    db.add(card)
    db.flush()

    state = ReviewState(
        card_id=card.id,
        streak=0,
        interval_days=1,
        next_review_at=datetime.utcnow(),
    )
    db.add(state)
    db.commit()
    db.refresh(card)

    return {"id": card.id, "topic_id": card.topic_id, "question": card.question, "answer": card.answer}


@app.get("/api/topics/{topic_id}/cards")
def list_topic_cards(topic_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    owned_topic_or_404(topic_id, current_user, db)
    cards = db.query(Card).filter(Card.topic_id == topic_id).order_by(Card.created_at.desc()).all()
    return [{"id": card.id, "question": card.question, "answer": card.answer} for card in cards]


@app.patch("/api/cards/{card_id}")
def update_card(card_id: int, payload: CardUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    card = owned_card_or_404(card_id, current_user, db)
    card.question = payload.question.strip()
    card.answer = payload.answer.strip()
    db.commit()
    db.refresh(card)
    return {"id": card.id, "topic_id": card.topic_id, "question": card.question, "answer": card.answer}


@app.delete("/api/cards/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    card = owned_card_or_404(card_id, current_user, db)
    db.query(ReviewState).filter(ReviewState.card_id == card_id).delete(synchronize_session=False)
    db.query(QuizResponse).filter(QuizResponse.card_id == card_id).delete(synchronize_session=False)
    db.delete(card)
    db.commit()
    return {"status": "ok"}


@app.post("/api/sessions/start")
def start_session(topic_id: int, limit: int = 5, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    owned_topic_or_404(topic_id, current_user, db)
    cards = (
        db.query(Card)
        .filter(Card.topic_id == topic_id)
        .order_by(func.random())
        .limit(max(1, min(limit, 20)))
        .all()
    )
    if not cards:
        return {"session_id": None, "cards": []}

    session = QuizSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)

    payload = [{"card_id": card.id, "question": card.question} for card in cards]
    return {"session_id": session.id, "cards": payload}


@app.post("/api/sessions/{session_id}/answer")
def answer_card(session_id: int, payload: AnswerRequest, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    session = owned_session_or_404(session_id, current_user, db)
    card = owned_card_or_404(payload.card_id, current_user, db)
    state = db.query(ReviewState).filter(ReviewState.card_id == payload.card_id).first()
    if not state:
        state = ReviewState(card_id=card.id, streak=0, interval_days=1, next_review_at=datetime.utcnow())
        db.add(state)
        db.flush()

    is_correct = evaluate_answer(card.answer, payload.user_answer)
    new_streak, new_interval = next_interval_after_answer(state.streak, is_correct)

    state.streak = new_streak
    state.interval_days = new_interval
    state.last_reviewed_at = datetime.utcnow()
    state.next_review_at = next_review_datetime(new_interval)

    response = QuizResponse(
        session_id=session.id,
        user_id=current_user.id,
        card_id=card.id,
        user_answer=payload.user_answer,
        is_correct=is_correct,
        response_seconds=max(0, payload.response_seconds),
    )
    db.add(response)
    db.commit()

    return {"is_correct": is_correct, "expected_answer": card.answer, "next_interval_days": new_interval}


@app.post("/api/sessions/{session_id}/finish")
def finish_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    session = owned_session_or_404(session_id, current_user, db)
    session.ended_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}


@app.get("/api/progress/summary")
def progress_summary(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    total_cards = (
        db.query(func.count(Card.id))
        .join(Topic, Card.topic_id == Topic.id)
        .filter(Topic.user_id == current_user.id)
        .scalar()
        or 0
    )
    due_cards = (
        db.query(func.count(ReviewState.id))
        .join(Card, ReviewState.card_id == Card.id)
        .join(Topic, Card.topic_id == Topic.id)
        .filter(Topic.user_id == current_user.id, ReviewState.next_review_at <= datetime.utcnow())
        .scalar()
        or 0
    )
    total_answers = db.query(func.count(QuizResponse.id)).filter(QuizResponse.user_id == current_user.id).scalar() or 0
    correct_answers = (
        db.query(func.count(QuizResponse.id))
        .filter(QuizResponse.user_id == current_user.id, QuizResponse.is_correct.is_(True))
        .scalar()
        or 0
    )
    incorrect_answers = max(0, total_answers - correct_answers)
    accuracy = round((correct_answers / total_answers) * 100, 1) if total_answers else 0.0

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=13)
    activity_rows = (
        db.query(func.date(QuizResponse.created_at), func.count(QuizResponse.id))
        .filter(QuizResponse.user_id == current_user.id, QuizResponse.created_at >= datetime.combine(start_date, datetime.min.time()))
        .group_by(func.date(QuizResponse.created_at))
        .order_by(func.date(QuizResponse.created_at))
        .all()
    )
    activity_map = {str(row[0]): row[1] for row in activity_rows}
    activity_by_day = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        activity_by_day.append({"date": key, "count": int(activity_map.get(key, 0))})

    return {
        "total_cards": total_cards,
        "due_today": due_cards,
        "total_answers": total_answers,
        "incorrect_answers": incorrect_answers,
        "accuracy_percent": accuracy,
        "activity_by_day": activity_by_day,
    }


@app.get("/api/forecast")
def forecast_summary(
    days: int = Query(default=14, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    progress = progress_summary(db=db, current_user=current_user)

    accuracy = float(progress.get("accuracy_percent", 0) or 0)
    due_today = int(progress.get("due_today", 0) or 0)
    total_answers = int(progress.get("total_answers", 0) or 0)
    total_cards = int(progress.get("total_cards", 0) or 0)
    incorrect = int(progress.get("incorrect_answers", 0) or 0)

    due_ratio = due_today / max(1, total_cards)
    base_score = 35 + accuracy * 0.55 + min(20, total_answers * 0.1) - min(18, due_ratio * 22) - min(10, incorrect * 0.3)
    retention = max(5, min(98, round(base_score - days * 0.55)))
    projected_due = max(due_today, round(due_today * (1 + days / 30)))

    top_topics = db.query(Topic).filter(Topic.user_id == current_user.id).order_by(Topic.id.asc()).limit(8).all()
    topic_risk = []
    for topic in top_topics:
        score = int((topic.id * 13 + days * 7 + total_answers * 3) % 100)
        topic_risk.append({"topic_id": topic.id, "title": topic.title, "risk_percent": score})

    explanation_steps = [
        "Step 1: Start with current accuracy as baseline retention quality.",
        "Step 2: Add stability bonus from total answer volume.",
        "Step 3: Subtract overload penalty from cards currently due.",
        "Step 4: Subtract confidence penalty from incorrect answers.",
        "Step 5: Apply time decay for the selected forecast horizon.",
    ]

    return {
        "days": days,
        "retention_percent": retention,
        "projected_due": projected_due,
        "topic_risk": sorted(topic_risk, key=lambda item: item["risk_percent"], reverse=True)[:4],
        "explanation_steps": explanation_steps,
    }


@app.get("/api/spaced-repetition-plan")
def get_spaced_repetition_plan(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """
    Returns a smart study plan organized by review windows:
    - Today (overdue + must review now)
    - Tomorrow (next 24 hours)
    - This Week (next 3-7 days)
    - Next Week (next 8-14 days)
    - Later (15+ days out)
    """
    now = datetime.utcnow()
    today = now.date()
    
    # Fetch all cards with their review states for this user
    cards_data = (
        db.query(Card, ReviewState, Topic)
        .join(ReviewState, Card.id == ReviewState.card_id)
        .join(Topic, Card.topic_id == Topic.id)
        .filter(Topic.user_id == current_user.id)
        .all()
    )
    
    # Organize into time windows
    time_windows = {
        "today": {"label": "Today", "start": today, "end": today, "cards": []},
        "tomorrow": {"label": "Tomorrow", "start": today + timedelta(days=1), "end": today + timedelta(days=1), "cards": []},
        "this_week": {"label": "This Week", "start": today + timedelta(days=2), "end": today + timedelta(days=6), "cards": []},
        "next_week": {"label": "Next Week", "start": today + timedelta(days=7), "end": today + timedelta(days=13), "cards": []},
        "later": {"label": "Later", "start": today + timedelta(days=14), "end": today + timedelta(days=365), "cards": []},
    }
    
    total_due = 0
    cards_due_today = 0
    
    # Sort cards into windows
    for card, review_state, topic in cards_data:
        review_date = review_state.next_review_at.date()
        days_until = (review_date - today).days
        
        # Determine which window this card belongs to
        window_key = None
        if days_until <= 0:
            window_key = "today"
            cards_due_today += 1
        elif days_until == 1:
            window_key = "tomorrow"
        elif 2 <= days_until <= 6:
            window_key = "this_week"
        elif 7 <= days_until <= 13:
            window_key = "next_week"
        else:
            window_key = "later"
        
        if window_key:
            total_due += 1
            card_info = {
                "card_id": card.id,
                "question": card.question,
                "answer": card.answer,
                "topic_id": topic.id,
                "topic_title": topic.title,
                "streak": review_state.streak,
                "interval_days": review_state.interval_days,
                "last_reviewed_at": review_state.last_reviewed_at.isoformat() if review_state.last_reviewed_at else None,
                "days_until_review": days_until,
            }
            time_windows[window_key]["cards"].append(card_info)
    
    # Sort cards within each window: due first, then by interval (higher first)
    for window in time_windows.values():
        window["cards"].sort(key=lambda x: (-x["days_until_review"], -x["interval_days"]))
    
    # Build response
    windows_list = []
    for key in ["today", "tomorrow", "this_week", "next_week", "later"]:
        window = time_windows[key]
        if window["cards"]:  # Only include windows with cards
            windows_list.append({
                "window_label": window["label"],
                "start_date": window["start"].isoformat(),
                "end_date": window["end"].isoformat(),
                "cards": window["cards"],
                "count": len(window["cards"]),
            })
    
    return {
        "generated_at": now.isoformat(),
        "total_cards_due": total_due,
        "time_windows": windows_list,
        "recommended_today": cards_due_today,
    }


@app.get("/api/insights")
def list_insights(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    entries = (
        db.query(InsightEntry)
        .filter(InsightEntry.user_id == current_user.id)
        .order_by(InsightEntry.created_at.desc())
        .all()
    )
    return [
        {
            "id": entry.id,
            "title": entry.title,
            "body": entry.body,
            "preview": entry.body[:140],
            "created_at": entry.created_at.isoformat(),
        }
        for entry in entries
    ]


@app.post("/api/insights")
def create_insight(payload: InsightEntryCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    entry = InsightEntry(user_id=current_user.id, title=payload.title.strip(), body=payload.body.strip())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "title": entry.title, "body": entry.body, "created_at": entry.created_at.isoformat()}


@app.get("/api/insights/{entry_id}")
def get_insight(entry_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    entry = owned_insight_or_404(entry_id, current_user, db)
    return {"id": entry.id, "title": entry.title, "body": entry.body, "created_at": entry.created_at.isoformat()}


@app.patch("/api/insights/{entry_id}")
def update_insight(entry_id: int, payload: InsightEntryUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    entry = owned_insight_or_404(entry_id, current_user, db)
    entry.title = payload.title.strip()
    entry.body = payload.body.strip()
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "title": entry.title, "body": entry.body, "created_at": entry.created_at.isoformat()}


@app.delete("/api/insights/{entry_id}")
def delete_insight(entry_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    entry = owned_insight_or_404(entry_id, current_user, db)
    db.delete(entry)
    db.commit()
    return {"status": "ok"}
