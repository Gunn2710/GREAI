"""Practice from the stored question bank: Verbal (Text Completion, Sentence
Equivalence, Reading Comprehension) and Quant (Quantitative Comparison,
multiple choice, numeric entry).

Each user has a rating per question type (verbal.tc, quant.qc, ...) on the same scale as
item difficulty. Questions are picked near the rating, preferring ones the
user hasn't seen; after each answer the user's rating and the item's learned
difficulty move toward what the answer implies (engine Elo updates).
Reading Comprehension questions on one passage are served together, in order.
"""
import math
import random
import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import vocab_engine as ve
from app.items import quant, verbal  # noqa: F401  (registers the practice item types)
from app.items.base import get_item_type
from app.models import Attempt, IssuedItem, Item, UserParams, UserSkill, utcnow
from app.seed.items import BANKS

KINDS = {kind: skill for kind, (_, skill, _) in BANKS.items()}
SECTION = {kind: section for kind, (_, _, section) in BANKS.items()}
KIND_NAMES = {
    "tc": "Text Completion", "se": "Sentence Equivalence", "rc": "Reading Comprehension",
    "qc": "Quantitative Comparison", "qmc": "Multiple Choice", "qne": "Numeric Entry",
}
# "mixed" (Verbal) and "quant" draw a type at random, roughly in the GRE's proportions.
MIXES = {
    "mixed": {"tc": 0.35, "se": 0.25, "rc": 0.4},
    "quant": {"qc": 0.35, "qmc": 0.45, "qne": 0.2},
}
RECENT_DAYS = 14                        # don't repeat a question within this window
ITEM_K = 0.05                           # how fast item difficulty learns


def guess_rate(item: Item) -> float:
    """Chance of answering right by pure guessing."""
    c = item.content
    match item.item_type:
        case "se":
            return 1 / 15  # one correct pair among C(6, 2)
        case "tc":
            n = len(c["blanks"])
            return 1 / 5 if n == 1 else (1 / 3) ** n
        case "qc":
            return 1 / 4
        case "qne":
            return 0.0
        case _:  # rc / qmc: one of 5, or one non-empty subset of the options
            return 1 / 5 if c["select"] == "one" else 1 / (2 ** len(c["options"]) - 1)


def get_skill(db: Session, user_id: str, skill_id: str) -> UserSkill:
    skill = db.get(UserSkill, (user_id, skill_id))
    if skill is None:
        # Verbal skills start from the vocabulary placement level when there is one.
        params = db.get(UserParams, user_id) if skill_id.startswith("verbal.") else None
        start = params.vocab_level if params and params.vocab_level is not None else 0.0
        skill = UserSkill(user_id=user_id, skill_id=skill_id, rating=start, attempts=0, correct=0)
        db.add(skill)
        db.flush()
    return skill


def _pick(db: Session, user_id: str, kind: str, rating: float) -> Item:
    items = list(db.scalars(select(Item).where(Item.item_type == kind, Item.status == "active")))
    if not items:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {KIND_NAMES[kind]} questions available")
    # Only answered questions count as seen: one fetched but abandoned (or
    # fetched twice by a remounting page) can still be served.
    last_seen = dict(db.execute(
        select(IssuedItem.bank_item_id, func.max(IssuedItem.answered_at))
        .where(
            IssuedItem.user_id == user_id, IssuedItem.item_type == kind,
            IssuedItem.answered_at.is_not(None),
        )
        .group_by(IssuedItem.bank_item_id)
    ).all())
    cutoff = utcnow() - timedelta(days=RECENT_DAYS)

    def seen_at(item: Item):
        return last_seen.get(item.id)

    unseen = [i for i in items if seen_at(i) is None]
    pool = unseen or [i for i in items if seen_at(i) < cutoff]
    if not pool:  # everything seen recently: repeat the oldest
        return min(items, key=seen_at)
    if kind == "rc":
        # Finish the passage in progress before starting another.
        last = max(last_seen, key=last_seen.get, default=None)
        passage = next((i.content["passage_slug"] for i in items if i.id == last), None)
        rest = [i for i in unseen if i.content["passage_slug"] == passage]
        if rest:
            return min(rest, key=lambda i: i.content["order"])
    rng = random.Random()
    chosen = min(pool, key=lambda i: abs(i.difficulty - rating) + rng.uniform(0, 0.5))
    if kind == "rc":  # start the chosen passage at its first question still in the pool
        same = [i for i in pool if i.content["passage_slug"] == chosen.content["passage_slug"]]
        chosen = min(same, key=lambda i: i.content["order"])
    return chosen


def _client_item(issued: IssuedItem, item: Item) -> dict:
    return {
        "id": issued.id,
        "item_type": issued.item_type,
        "kind_name": KIND_NAMES[issued.item_type],
        "payload": issued.payload,
        "hint_available": True,
    }


def next_item(db: Session, user_id: str, kind: str) -> dict:
    if kind in MIXES:
        kind = random.choices(list(MIXES[kind]), weights=MIXES[kind].values())[0]
    if kind not in KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"kind must be one of {[*KINDS, *MIXES]}")
    skill = get_skill(db, user_id, KINDS[kind])
    item = _pick(db, user_id, kind, skill.rating)
    built = get_item_type(kind).build(db, user_id, item)
    issued = IssuedItem(
        id=str(uuid.uuid4()), user_id=user_id, section=SECTION[kind], item_type=kind,
        bank_item_id=item.id, payload=built.payload, answer=built.answer,
    )
    db.add(issued)
    db.commit()
    return {"item": _client_item(issued, item)}


def _open(db: Session, user_id: str, issued_id: str) -> IssuedItem:
    issued = db.get(IssuedItem, issued_id)
    if issued is None or issued.user_id != user_id or issued.item_type not in KINDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if issued.answered_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Item already answered")
    return issued


def hint(db: Session, user_id: str, issued_id: str) -> dict:
    issued = _open(db, user_id, issued_id)
    issued.hint_used = True
    db.commit()
    return get_item_type(issued.item_type).hint(issued)


async def answer(db: Session, user_id: str, issued_id: str, response: dict, response_ms: int) -> dict:
    issued = _open(db, user_id, issued_id)
    item = db.get(Item, issued.bank_item_id)
    grade = await get_item_type(issued.item_type).grade(db, issued, response)

    skill = get_skill(db, user_id, KINDS[issued.item_type])
    before, b, guess = skill.rating, item.difficulty, guess_rate(item)
    k = max(0.15, 0.8 / math.sqrt(skill.attempts + 1))
    if issued.hint_used:
        k /= 2  # a hinted answer is weaker evidence
    skill.rating = ve.update_ability(before, b, grade.correct, guess=guess, k=k)
    skill.attempts += 1
    skill.correct += int(grade.correct)
    item.difficulty_offset = ve.update_difficulty(b, before, grade.correct, guess=guess, k=ITEM_K) - item.difficulty_prior

    issued.answered_at = utcnow()
    db.add(Attempt(
        user_id=user_id, item_id=issued.id, section=SECTION[issued.item_type], item_type=issued.item_type,
        correct=grade.correct, score=grade.score, response_ms=int(response_ms),
        hint_used=issued.hint_used, response=response,
    ))
    db.commit()
    return {
        "correct": grade.correct,
        "feedback": grade.feedback,
        "difficulty": item.difficulty_label,
        "rating_before": round(before, 2),
        "rating_after": round(skill.rating, 2),
    }


def summary(db: Session, user_id: str) -> dict:
    out = {}
    for kind, skill_id in KINDS.items():
        skill = db.get(UserSkill, (user_id, skill_id))
        total = db.scalar(select(func.count()).select_from(Item).where(Item.item_type == kind)) or 0
        out[kind] = {
            "name": KIND_NAMES[kind],
            "section": SECTION[kind],
            "rating": round(skill.rating, 2) if skill else None,
            "attempts": skill.attempts if skill else 0,
            "accuracy": round(skill.correct / skill.attempts, 3) if skill and skill.attempts else None,
            "questions": total,
        }
    return out
