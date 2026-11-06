"""Study loop: pick the next word and quiz mode, grade answers, update the model."""
import random
import uuid
from datetime import datetime, time, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import engine_bridge as eb
from app import vocab_engine as ve
from app.config import get_settings
from app.items import vocab  # noqa: F401  (registers vocab item types)
from app.items.base import get_item_type
from app.models import Attempt, Card, Confusion, IssuedItem, Profile, UserParams, Word, utcnow
from app.services.ai import claude
from app.services.difficulty import FAST_TRACK_P, known_card, word_difficulty

# If a mode can't be built for a word (e.g. no example sentence for cloze),
# fall back to the next mode down the ladder.
FALLBACK_CHAIN = ["usage", "synonyms", "cloze", "meaning", "flashcard"]


def word_detail(word: Word) -> dict:
    return {
        "id": word.id,
        "lemma": word.lemma,
        "pos": word.pos,
        "pronunciation": word.pronunciation,
        "definition": word.definition,
        "nuance": word.nuance,
        "examples": word.examples,
        "synonyms": word.synonyms,
        "antonyms": word.antonyms,
        "confusables": word.confusables,
        "cluster": word.cluster,
        "tier": word.tier,
    }


def get_profile(db: Session, user_id: str) -> Profile:
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, daily_new_words=get_settings().default_daily_new_words)
        db.add(profile)
        db.commit()
    return profile


def get_params(db: Session, user_id: str) -> UserParams:
    params = db.get(UserParams, user_id)
    if params is None:
        params = UserParams(user_id=user_id, speed_baselines={})
        db.add(params)
        db.flush()
    return params


def start_of_today() -> datetime:
    return datetime.combine(utcnow().date(), time.min, tzinfo=timezone.utc)


def _cards_started_today(db: Session, user_id: str, fast_tracked: bool) -> int:
    origin = Card.origin.in_(("placement", "fast_track"))
    return db.scalar(
        select(func.count()).select_from(Card).where(
            Card.user_id == user_id,
            Card.created_at >= start_of_today(),
            origin if fast_tracked else or_(Card.origin.is_(None), Card.origin == "study"),
        )
    ) or 0


def new_words_started_today(db: Session, user_id: str) -> int:
    """New words that count toward the daily limit (fast-tracked ones don't)."""
    return _cards_started_today(db, user_id, fast_tracked=False)


def _last_word_id(db: Session, user_id: str) -> int | None:
    return db.scalar(
        select(IssuedItem.word_id).where(IssuedItem.user_id == user_id)
        .order_by(IssuedItem.issued_at.desc()).limit(1)
    )


def _pick_due_card(db: Session, user_id: str, now: float) -> Card | None:
    due = list(db.scalars(select(Card).where(Card.user_id == user_id, Card.due <= utcnow())))
    if not due:
        return None
    last = _last_word_id(db, user_id)
    if len(due) > 1:
        due = [c for c in due if c.word_id != last] or due
    return max(due, key=lambda c: eb.model.priority(eb.card_to_engine(c), now))


def _start_new_card(db: Session, user_id: str) -> Card | None:
    """Introduce the next unseen word, most frequent first.

    If the user's placement level says they very likely know it, it is
    fast-tracked: no flashcard, straight to a recall check. Fast-tracked words
    don't use the daily new-word allowance but are capped at twice it.
    """
    profile = get_profile(db, user_id)
    seen = select(Card.word_id).where(Card.user_id == user_id)
    word = db.scalar(
        select(Word).where(Word.id.not_in(seen)).order_by(Word.tier, Word.id).limit(1)
    )
    if word is None:
        return None

    theta = get_params(db, user_id).vocab_level
    if (theta is not None
            and ve.p_know(theta, word_difficulty(word)) >= FAST_TRACK_P
            and _cards_started_today(db, user_id, fast_tracked=True) < 2 * profile.daily_new_words):
        card = known_card(user_id, word.id, "fast_track", due_in_days=0)
    elif new_words_started_today(db, user_id) < profile.daily_new_words:
        card = Card(user_id=user_id, word_id=word.id, due=utcnow(), origin="study")
    else:
        return None
    db.add(card)
    db.flush()
    return card


def _client_item(item: IssuedItem) -> dict:
    return {
        "id": item.id,
        "item_type": item.item_type,
        "section": item.section,
        "payload": item.payload,
        "hint_available": get_item_type(item.item_type).hint_available,
    }


def next_item(db: Session, user_id: str) -> dict:
    now = eb.now_days()
    card = _pick_due_card(db, user_id, now) or _start_new_card(db, user_id)
    if card is None:
        next_due = db.scalar(select(func.min(Card.due)).where(Card.user_id == user_id))
        return {"done": True, "next_due": next_due.isoformat() if next_due else None}

    word = db.get(Word, card.word_id)
    mode = eb.model.choose_mode(eb.card_to_engine(card), random.random(), claude.enabled)
    chain = FALLBACK_CHAIN[FALLBACK_CHAIN.index(eb.NAME_BY_MODE[mode]):]

    built, type_name = None, None
    for type_name in chain:
        built = get_item_type(type_name).build(db, user_id, word)
        if built is not None:
            break
    if type_name == "flashcard":
        built.payload["back"] = word_detail(word)

    item = IssuedItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        section="verbal",
        item_type=type_name,
        word_id=word.id,
        payload=built.payload,
        answer=built.answer,
    )
    card.last_mode = type_name
    db.add(item)
    db.commit()
    return {
        "done": False,
        "item": _client_item(item),
        "is_new_word": card.reps == 0,
        "likely_known": card.reps == 1 and card.origin in ("placement", "fast_track"),
        "card": eb.card_summary(card, now),
    }


def _get_open_item(db: Session, user_id: str, item_id: str) -> IssuedItem:
    item = db.get(IssuedItem, item_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if item.answered_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Item already answered")
    return item


def hint(db: Session, user_id: str, item_id: str) -> dict:
    item = _get_open_item(db, user_id, item_id)
    data = get_item_type(item.item_type).hint(item)
    if data is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No hint for this item")
    item.hint_used = True
    db.commit()
    return data


def _record_confusions(db: Session, user_id: str, target_id: int, chosen_ids: list[int]) -> None:
    for chosen_id in chosen_ids:
        row = db.get(Confusion, (user_id, target_id, chosen_id))
        if row is None:
            row = Confusion(user_id=user_id, target_word_id=target_id, chosen_word_id=chosen_id, count=0)
            db.add(row)
        row.count += 1
        row.last_at = utcnow()


async def answer(
    db: Session,
    user_id: str,
    item_id: str,
    response: dict,
    response_ms: int,
    confidence: str | None,
) -> dict:
    item = _get_open_item(db, user_id, item_id)
    grade = await get_item_type(item.item_type).grade(db, item, response)

    card = db.get(Card, (user_id, item.word_id))
    params = get_params(db, user_id)

    ev = ve.Evidence()
    ev.mode = eb.MODE_BY_NAME[item.item_type]
    ev.correct = grade.correct
    ev.response_ms = float(max(0, response_ms))
    ev.hint_used = item.hint_used
    ev.confidence = eb.CONFIDENCE_BY_NAME.get(confidence, ve.Confidence.None_)
    ev.self_rating = grade.self_rating

    now = eb.now_days()
    outcome = eb.model.process(
        eb.card_to_engine(card), ev, eb.baselines_from_json(params.speed_baselines), now
    )
    eb.apply_engine_card(card, outcome.card)
    params.speed_baselines = eb.baselines_to_json(outcome.baselines)
    _record_confusions(db, user_id, item.word_id, grade.chosen_word_ids)

    item.answered_at = utcnow()
    db.add(Attempt(
        user_id=user_id,
        item_id=item.id,
        section=item.section,
        item_type=item.item_type,
        word_id=item.word_id,
        correct=grade.correct,
        score=grade.score,
        rating=int(outcome.rating),
        response_ms=int(ev.response_ms),
        confidence=int(ev.confidence),
        hint_used=item.hint_used,
        response=response,
        comfort_before=outcome.comfort_before,
        comfort_after=outcome.comfort_after,
    ))
    db.commit()

    return {
        "correct": grade.correct,
        "score": grade.score,
        "rating": outcome.rating.name.lower(),
        "promoted": outcome.promoted,
        "demoted": outcome.demoted,
        "comfort_before": round(outcome.comfort_before, 1),
        "comfort_after": round(outcome.comfort_after, 1),
        "feedback": grade.feedback,
        "card": eb.card_summary(card, now),
        "word": word_detail(db.get(Word, item.word_id)),
    }
