from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.config import get_settings
from app.db import get_db
from app.models import Word
from app.services import coach, placement, practice, sets, stats, study
from app.services.ai import claude

router = APIRouter(prefix="/api")


# ---- config / profile ------------------------------------------------------

@router.get("/config")
def config():
    s = get_settings()
    return {"ai_enabled": s.ai_enabled, "auth_mode": s.auth_mode, "model": s.claude_model}


@router.get("/me")
def me(user_id: str = Depends(current_user_id)):
    """Who the API thinks you are. 401 if not signed in, 403 if not approved."""
    return {"user_id": user_id}


class ProfileIn(BaseModel):
    test_date: date | None = None
    target_verbal: int | None = Field(default=None, ge=130, le=170)
    target_quant: int | None = Field(default=None, ge=130, le=170)
    daily_new_words: int = Field(default=10, ge=0, le=100)


def _profile_out(p) -> dict:
    return {
        "test_date": p.test_date.isoformat() if p.test_date else None,
        "target_verbal": p.target_verbal,
        "target_quant": p.target_quant,
        "daily_new_words": p.daily_new_words,
    }


@router.get("/me/profile")
def read_profile(user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return _profile_out(study.get_profile(db, user_id))


@router.put("/me/profile")
def update_profile(body: ProfileIn, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    p = study.get_profile(db, user_id)
    for key, value in body.model_dump().items():
        setattr(p, key, value)
    db.commit()
    return _profile_out(p)


# ---- study loop -------------------------------------------------------------

@router.get("/study/next")
def next_item(format: Literal["mixed", "flashcard", "mcq"] = "mixed",
              user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return study.next_item(db, user_id, format)


class StudyMoreIn(BaseModel):
    words: int = Field(default=5, ge=1, le=50)


@router.post("/study/more")
def study_more(body: StudyMoreIn, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    """Allow more new words today, past the daily limit."""
    return study.study_more(db, user_id, body.words)


@router.post("/study/items/{item_id}/hint")
def hint(item_id: str, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return study.hint(db, user_id, item_id)


class AnswerIn(BaseModel):
    response: dict
    response_ms: int = Field(ge=0, le=3_600_000)
    confidence: Literal["sure", "unsure", "guess"] | None = None


@router.post("/study/items/{item_id}/answer")
async def answer(item_id: str, body: AnswerIn, user_id: str = Depends(current_user_id),
                 db: Session = Depends(get_db)):
    return await study.answer(db, user_id, item_id, body.response, body.response_ms, body.confidence)


@router.get("/stats")
def dashboard(user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return stats.dashboard(db, user_id)


# ---- practice (Verbal and Quant question types) -----------------------------

PracticeKind = Literal["tc", "se", "rc", "mixed", "qc", "qmc", "qne", "quant"]


@router.get("/practice/next")
def practice_next(kind: PracticeKind = "mixed", user_id: str = Depends(current_user_id),
                  db: Session = Depends(get_db)):
    return practice.next_item(db, user_id, kind)


@router.post("/practice/items/{item_id}/hint")
def practice_hint(item_id: str, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return practice.hint(db, user_id, item_id)


class PracticeAnswerIn(BaseModel):
    response: dict
    response_ms: int = Field(ge=0, le=3_600_000)


@router.post("/practice/items/{item_id}/answer")
async def practice_answer(item_id: str, body: PracticeAnswerIn, user_id: str = Depends(current_user_id),
                          db: Session = Depends(get_db)):
    return await practice.answer(db, user_id, item_id, body.response, body.response_ms)


@router.get("/practice/summary")
def practice_summary(user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return practice.summary(db, user_id)


# ---- placement --------------------------------------------------------------

@router.post("/placement/start")
def placement_start(user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return placement.start(db, user_id)


class PlacementAnswerIn(BaseModel):
    item_id: str
    selected: int | None = Field(default=None, ge=0, le=9)  # None = "I don't know"
    response_ms: int = Field(ge=0, le=3_600_000)


@router.post("/placement/{run_id}/answer")
def placement_answer(run_id: str, body: PlacementAnswerIn, user_id: str = Depends(current_user_id),
                     db: Session = Depends(get_db)):
    return placement.answer(db, user_id, run_id, body.item_id, body.selected, body.response_ms)


@router.get("/placement/latest")
def placement_latest(user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return {"result": placement.latest(db, user_id)}


# ---- words ------------------------------------------------------------------

@router.get("/sets")
def word_sets(user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return sets.word_sets(db, user_id)


@router.get("/words")
def words(search: str | None = None, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return stats.word_list(db, user_id, search)


def _word_or_404(db: Session, word_id: int) -> Word:
    word = db.get(Word, word_id)
    if word is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Word not found")
    return word


@router.get("/words/{word_id}")
def word(word_id: int, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    w = _word_or_404(db, word_id)
    entry = next((x for x in stats.word_list(db, user_id, w.lemma) if x["id"] == w.id), None)
    return {"word": study.word_detail(w), "card": entry["card"] if entry else None,
            "my_sentence": study.my_sentence(db, user_id, w.id)}


class SentenceIn(BaseModel):
    sentence: str = Field(max_length=study.MAX_SENTENCE)


@router.put("/words/{word_id}/sentence")
def save_sentence(word_id: int, body: SentenceIn, user_id: str = Depends(current_user_id),
                  db: Session = Depends(get_db)):
    """Your own sentence with the word, to help you remember it. Empty removes it."""
    w = _word_or_404(db, word_id)
    return {"my_sentence": study.save_sentence(db, user_id, w.id, body.sentence)}


# ---- AI -----------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class CoachIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    # What's on screen: the Vocab or Practice question being worked on, or the word page being read.
    study_item_id: str | None = Field(default=None, max_length=36)
    practice_item_id: str | None = Field(default=None, max_length=36)
    word_id: int | None = None


@router.post("/coach/chat")
async def coach_chat(body: CoachIn, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    """The study coach (chat bubble): progress, planning, GRE and vocabulary help."""
    if body.messages[-1].role != "user":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Last message must be from the user")
    return await coach.chat(db, user_id, [m.model_dump() for m in body.messages],
                            study_item_id=body.study_item_id, practice_item_id=body.practice_item_id,
                            word_id=body.word_id)


@router.post("/words/{word_id}/mnemonic")
async def mnemonic(word_id: int, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)):
    return {"mnemonic": await claude.mnemonic(_word_or_404(db, word_id))}
