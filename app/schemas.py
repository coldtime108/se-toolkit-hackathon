from pydantic import BaseModel, Field


class AuthRegister(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class AuthLogin(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class TopicCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)


class TopicUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=200)


class NoteCreate(BaseModel):
    content: str = Field(min_length=10)


class CardCreate(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=250)


class CardUpdate(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=250)


class InsightEntryCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    body: str = Field(min_length=5, max_length=5000)


class InsightEntryUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    body: str = Field(min_length=5, max_length=5000)


class AnswerRequest(BaseModel):
    card_id: int
    user_answer: str = Field(min_length=1, max_length=250)
    response_seconds: float = 0


class CardWithReviewState(BaseModel):
    card_id: int
    question: str
    answer: str
    topic_id: int
    topic_title: str
    streak: int
    interval_days: int
    last_reviewed_at: str | None
    days_until_review: int


class ReviewTimeWindow(BaseModel):
    window_label: str  # "Today", "Tomorrow", "This Week"
    start_date: str
    end_date: str
    cards: list[CardWithReviewState]
    count: int


class SpacedRepetitionPlan(BaseModel):
    generated_at: str
    total_cards_due: int
    time_windows: list[ReviewTimeWindow]
    recommended_today: int


class GeneratedCardDraft(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=250)


class QuizGenerationPreviewRequest(BaseModel):
    text: str = Field(min_length=10, max_length=12000)
    limit: int = Field(default=10, ge=1, le=30)


class QuizGenerationSaveRequest(BaseModel):
    topic_id: int
    cards: list[GeneratedCardDraft] = Field(min_length=1, max_length=30)
