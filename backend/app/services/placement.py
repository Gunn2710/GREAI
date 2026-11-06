"""Adaptive placement check.

Asks 20 "pick the definition" questions, each chosen near the current
ability estimate, and estimates the user's vocabulary level (theta) with the
engine's IRT model. Words answered correctly become cards that skip the
learning steps, and every answer nudges the word's global difficulty so the
bank's difficulty estimates improve as more people take the check.

Word difficulty lives in app/services/difficulty.py.
"""
import random
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import vocab_engine as ve
from app.items.base import get_item_type
from app.models import Card, IssuedItem, PlacementRun, Word, utcnow
from app.services.difficulty import known_card, tier_prior, word_difficulty
from app.services.study import get_params, word_detail

GUESS = 0.2                # chance of guessing right among 4 definitions + "I don't know"
# Simulations with the current bank (three difficulty levels from the tier
# priors) give about +/-0.45 accuracy after 20 questions for typical users,
# and underestimate very strong users; early stopping on the posterior SD
# never triggered, so the length is fixed.
QUESTIONS = 20
KNOWN_RECHECK_DAYS = 2     # placement-known words come back for a check this soon

LEVELS = [(-0.5, "Building"), (0.5, "Developing"), (1.5, "Strong"), (float("inf"), "Advanced")]


def level_label(theta: float) -> str:
    return next(label for bound, label in LEVELS if theta < bound)


def _estimate(run: PlacementRun) -> ve.AbilityEstimate:
    return ve.estimate_ability(
        [ve.IrtResponse(r["b"], r["correct"]) for r in run.responses], guess=GUESS
    )


def _open_run(db: Session, user_id: str, run_id: str) -> PlacementRun:
    run = db.get(PlacementRun, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Placement run not found")
    if run.finished_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Placement run already finished")
    return run


def _next_word(db: Session, user_id: str, run: PlacementRun, theta: float) -> Word | None:
    asked = {r["word_id"] for r in run.responses}
    known = set(db.scalars(select(Card.word_id).where(Card.user_id == user_id)))
    candidates = [w for w in db.scalars(select(Word)) if w.id not in asked and w.id not in known]
    if not candidates:
        return None
    # Most informative items sit near theta; jitter avoids always picking one tier.
    rng = random.Random()
    return min(candidates, key=lambda w: abs(word_difficulty(w) - theta) + rng.uniform(0, 0.4))


def _issue(db: Session, user_id: str, run: PlacementRun, word: Word) -> dict:
    built = get_item_type("meaning").build(db, user_id, word)
    item = IssuedItem(
        id=str(uuid.uuid4()), user_id=user_id, section="verbal", item_type="placement",
        word_id=word.id, payload={**built.payload, "run_id": run.id}, answer=built.answer,
    )
    db.add(item)
    db.commit()
    return {
        "id": item.id,
        "word": word.lemma,
        "pos": word.pos,
        "pronunciation": word.pronunciation,
        "options": built.payload["options"],
        "number": len(run.responses) + 1,
        "max": QUESTIONS,
    }


def start(db: Session, user_id: str) -> dict:
    for old in db.scalars(select(PlacementRun).where(
        PlacementRun.user_id == user_id, PlacementRun.finished_at.is_(None)
    )):
        db.delete(old)  # abandon unfinished attempts
    run = PlacementRun(id=str(uuid.uuid4()), user_id=user_id, responses=[])
    db.add(run)
    db.commit()
    word = _next_word(db, user_id, run, 0.0)
    if word is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No unseen words left to test")
    return {"run_id": run.id, "done": False, "item": _issue(db, user_id, run, word)}


def answer(db: Session, user_id: str, run_id: str, item_id: str,
           selected: int | None, response_ms: int) -> dict:
    run = _open_run(db, user_id, run_id)
    item = db.get(IssuedItem, item_id)
    if (item is None or item.user_id != user_id or item.item_type != "placement"
            or item.payload.get("run_id") != run.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if item.answered_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Item already answered")

    word = db.get(Word, item.word_id)
    correct = selected is not None and selected == item.answer["index"]
    b = word_difficulty(word)
    theta_before = _estimate(run).theta
    # Learn the word's difficulty from this answer (stored as an offset from the tier prior).
    new_b = ve.update_difficulty(b, theta_before, correct, guess=GUESS)
    word.global_difficulty = new_b - tier_prior(word)

    run.responses = [*run.responses, {
        "word_id": word.id, "b": b, "correct": correct,
        "dont_know": selected is None, "ms": int(response_ms),
    }]
    item.answered_at = utcnow()
    db.commit()

    est = _estimate(run)
    nxt = None
    if len(run.responses) < QUESTIONS:
        nxt = _next_word(db, user_id, run, est.theta)
    if nxt is None:
        return {"done": True, "result": _finish(db, user_id, run, est)}
    return {"done": False, "item": _issue(db, user_id, run, nxt)}


def _finish(db: Session, user_id: str, run: PlacementRun, est: ve.AbilityEstimate) -> dict:
    run.theta, run.se, run.finished_at = est.theta, est.se, utcnow()
    get_params(db, user_id).vocab_level = est.theta

    fast = 0
    for r in run.responses:
        if r["correct"] and db.get(Card, (user_id, r["word_id"])) is None:
            db.add(known_card(user_id, r["word_id"], "placement", KNOWN_RECHECK_DAYS))
            fast += 1
    run.fast_tracked = fast
    db.commit()
    return summary(db, run)


def summary(db: Session, run: PlacementRun) -> dict:
    words = list(db.scalars(select(Word)))
    by_tier: dict[int, list[float]] = {}
    for w in words:
        by_tier.setdefault(w.tier, []).append(ve.p_know(run.theta, word_difficulty(w)))
    asked = {r["word_id"]: r for r in run.responses}
    return {
        "run_id": run.id,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "theta": round(run.theta, 2),
        "se": round(run.se, 2),
        "level": level_label(run.theta),
        "answered": len(run.responses),
        "correct": sum(r["correct"] for r in run.responses),
        "fast_tracked": run.fast_tracked,
        # Expected share of each frequency tier the user already knows.
        "known_share": {str(t): round(sum(ps) / len(ps), 2) for t, ps in sorted(by_tier.items())},
        "missed": [
            word_detail(db.get(Word, wid)) for wid, r in asked.items() if not r["correct"]
        ][:8],
    }


def latest(db: Session, user_id: str) -> dict | None:
    run = db.scalar(
        select(PlacementRun)
        .where(PlacementRun.user_id == user_id, PlacementRun.finished_at.is_not(None))
        .order_by(PlacementRun.finished_at.desc()).limit(1)
    )
    return summary(db, run) if run else None
