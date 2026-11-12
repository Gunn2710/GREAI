"""Database schema (PostgreSQL / Supabase).

User ids are opaque strings (Clerk user ids), so there are no foreign keys to
an auth table.
"""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    test_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_verbal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_quant: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_new_words: Mapped[int] = mapped_column(Integer, default=10)
    # "Study more": new words added on top of the daily limit, for one day only.
    extra_new_words: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    extra_new_words_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Skill(Base):
    """Skill taxonomy tree shared by every section (verbal.vocab.*, quant.*, writing.*)."""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    section: Mapped[str] = mapped_column(String(16))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128))


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lemma: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    pos: Mapped[str] = mapped_column(String(16))
    # Stress-marked respelling, e.g. "luh-KAH-nik"; variants joined by " or ".
    pronunciation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    definition: Mapped[str] = mapped_column(Text)
    nuance: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[list] = mapped_column(JSONB, default=list)
    # The most common ways the word is actually used, e.g. "widely lauded".
    phrases: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    synonyms: Mapped[list] = mapped_column(JSONB, default=list)
    antonyms: Mapped[list] = mapped_column(JSONB, default=list)
    confusables: Mapped[list] = mapped_column(JSONB, default=list)
    cluster: Mapped[str] = mapped_column(String(64), index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    tier: Mapped[int] = mapped_column(Integer, default=1)  # 1 = most common on the GRE
    global_difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    # Study sets: GregMat's groups, then the rest most common first (assigned
    # by the bank sync, see app/seed/seed.py). set_rank is the word's place in the whole order.
    set_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    set_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Item(Base):
    """A stored question (Verbal: TC, SE, RC; Quant: comparison, multiple choice, numeric entry)."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    section: Mapped[str] = mapped_column(String(16))
    item_type: Mapped[str] = mapped_column(String(32), index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    difficulty_label: Mapped[str] = mapped_column(String(16))  # easy / medium / hard
    difficulty_prior: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty_offset: Mapped[float] = mapped_column(Float, default=0.0)  # learned from answers
    content: Mapped[dict] = mapped_column(JSONB)  # authored content; see app/seed/verbal, app/seed/quant
    status: Mapped[str] = mapped_column(String(16), default="active")

    @property
    def difficulty(self) -> float:
        return self.difficulty_prior + (self.difficulty_offset or 0.0)


class UserSkill(Base):
    """A user's rating on one skill (same scale as item difficulty)."""

    __tablename__ = "user_skills"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)


class Card(Base):
    """Per-user, per-word memory + comfort state (mirrors vocab_engine.WordCard)."""

    __tablename__ = "cards"
    __table_args__ = (Index("ix_cards_user_due", "user_id", "due"),)

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), primary_key=True)

    state: Mapped[int] = mapped_column(Integer, default=0)
    step: Mapped[int] = mapped_column(Integer, default=0)
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)

    depth: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_streak_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calibration: Mapped[float] = mapped_column(Float, default=0.5)
    last_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # How the card started: "study" (new word), "placement" (answered right in
    # the placement check) or "fast_track" (predicted known from vocab level).
    # Only "study" cards count toward the daily new-word limit. NULL = "study".
    origin: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IssuedItem(Base):
    """A question served to a user. The answer key never leaves the server."""

    __tablename__ = "issued_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    section: Mapped[str] = mapped_column(String(16))
    item_type: Mapped[str] = mapped_column(String(32))
    word_id: Mapped[int | None] = mapped_column(ForeignKey("words.id"), nullable=True)
    bank_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    answer: Mapped[dict] = mapped_column(JSONB)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Attempt(Base):
    """Log of every answered item, for every section."""

    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    item_id: Mapped[str] = mapped_column(String(36))
    section: Mapped[str] = mapped_column(String(16))
    item_type: Mapped[str] = mapped_column(String(32))
    word_id: Mapped[int | None] = mapped_column(ForeignKey("words.id"), nullable=True)
    correct: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_ms: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)
    response: Mapped[dict] = mapped_column(JSONB, default=dict)
    comfort_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    comfort_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WordSentence(Base):
    """A sentence the student wrote with a word to help them remember it (optional)."""

    __tablename__ = "word_sentences"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), primary_key=True)
    sentence: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CoachMessage(Base):
    """One message in a student's chat with the study coach, kept so the chat survives a refresh."""

    __tablename__ = "coach_messages"
    __table_args__ = (Index("ix_coach_messages_user_id_id", "user_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)
    # A plan change the coach suggested with this reply (see coach.propose_plan).
    proposal: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Confusion(Base):
    """Which wrong word a user picked when the answer was another word."""

    __tablename__ = "confusions"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), primary_key=True)
    chosen_word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlacementRun(Base):
    """One adaptive placement check: the answers and the resulting ability estimate."""

    __tablename__ = "placement_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    theta: Mapped[float] = mapped_column(Float, default=0.0)
    se: Mapped[float] = mapped_column(Float, default=1.0)
    # [{"word_id", "b", "correct", "dont_know", "ms"}, ...]
    responses: Mapped[list] = mapped_column(JSONB, default=list)
    fast_tracked: Mapped[int] = mapped_column(Integer, default=0)


class UserParams(Base):
    """Personalized model parameters learned per user."""

    __tablename__ = "user_params"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    speed_baselines: Mapped[dict] = mapped_column(JSONB, default=dict)
    fsrs_weights: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    vocab_level: Mapped[float | None] = mapped_column(Float, nullable=True)
