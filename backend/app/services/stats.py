"""Dashboard numbers: comfort tiers, depth ladder, due forecast, accuracy, streak, check-ins."""
from collections import Counter
from datetime import timedelta

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app import engine_bridge as eb
from app.models import Attempt, Card, Word, utcnow
from app.services.sets import word_sets
from app.services.study import get_profile, new_word_limit, new_words_started_today, start_of_today, word_detail

TIERS = ["new", "learning", "shaky", "comfortable", "mastered"]
VOCAB_TYPES = ("flashcard", "meaning", "cloze", "synonyms", "usage")


def _as_utc(dt):
    return eb.from_days(eb.to_days(dt))


def _utc_day(column):
    """A timestamp column as its UTC calendar day, in SQL."""
    return func.date(func.timezone("UTC", column))


def _streak_days(db: Session, user_id: str) -> int:
    # Only the distinct days come back, not every answer.
    day = _utc_day(Attempt.created_at)
    days = set(
        db.scalars(
            select(day)
            .where(Attempt.user_id == user_id, Attempt.created_at >= utcnow() - timedelta(days=400))
            .group_by(day)
        )
    )
    today = utcnow().date()
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


ACTIVITY_DAYS = 126  # 18 weeks, about four months


def _activity(db: Session, user_id: str) -> dict:
    """Words studied on each day (UTC, like the streak), for the check-in grid. Only
    days with studying are listed."""
    today = utcnow().date()
    day = _utc_day(Attempt.created_at)
    rows = db.execute(
        select(day, func.count(func.distinct(Attempt.word_id)))
        .where(
            Attempt.user_id == user_id,
            Attempt.item_type.in_(VOCAB_TYPES),
            Attempt.word_id.is_not(None),
            Attempt.created_at >= start_of_today() - timedelta(days=ACTIVITY_DAYS - 1),
        )
        .group_by(day)
        .order_by(day)
    )
    return {
        "today": today.isoformat(),
        "days": [{"date": d.isoformat(), "words": n} for d, n in rows],
    }


def dashboard(db: Session, user_id: str) -> dict:
    now = eb.now_days()
    now_dt = utcnow()
    profile = get_profile(db, user_id)
    total_words = db.scalar(select(func.count()).select_from(Word)) or 0
    cards = list(db.scalars(select(Card).where(Card.user_id == user_id)))

    tiers: Counter = Counter()
    depth: Counter = Counter()
    summaries = []
    for card in cards:
        s = eb.card_summary(card, now)
        tiers[s["tier"]] += 1
        depth[s["depth_name"]] += 1
        summaries.append((card, s))
    tiers["new"] += total_words - len(cards)

    end_of_today = start_of_today() + timedelta(days=1)
    due_now = sum(1 for c in cards if _as_utc(c.due) <= now_dt)
    forecast = []
    for i in range(7):
        start = start_of_today() + timedelta(days=i)
        end = start + timedelta(days=1)
        forecast.append({
            "date": start.date().isoformat(),
            "due": sum(1 for c in cards if c.reps > 0 and start <= _as_utc(c.due) < end),
        })

    # Counted in SQL: a month of answers can be thousands of rows.
    answered, right, reviews_today = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(Attempt.correct.cast(Integer)), 0),
            func.count().filter(Attempt.created_at >= start_of_today()),
        ).where(
            Attempt.user_id == user_id,
            Attempt.created_at >= now_dt - timedelta(days=30),
            Attempt.item_type.in_(VOCAB_TYPES),
        )
    ).one()
    accuracy = round(right / answered, 3) if answered else None

    weakest = sorted(
        (x for x in summaries if x[0].reps > 0), key=lambda x: x[1]["comfort"]
    )[:5]
    words = {w.id: w for w in db.scalars(select(Word).where(Word.id.in_([c.word_id for c, _ in weakest])))}
    new_left = max(0, min(new_word_limit(profile) - new_words_started_today(db, user_id),
                          total_words - len(cards)))

    sets = word_sets(db, user_id, summaries={c.word_id: (c, s) for c, s in summaries})
    return {
        "total_words": total_words,
        "sets": {
            "total": len(sets["sets"]),
            "done": sum(s["status"] == "done" for s in sets["sets"]),
            "current": next((s for s in sets["sets"] if s["number"] == sets["current"]), None),
        },
        "tiers": {t: tiers.get(t, 0) for t in TIERS},
        "depth": {d: depth.get(d, 0) for d in eb.DEPTH_NAMES},
        "due_now": due_now,
        "due_today": sum(1 for c in cards if _as_utc(c.due) < end_of_today),
        "new_available_today": new_left,
        "reviews_today": reviews_today,
        "accuracy_30d": accuracy,
        "streak_days": _streak_days(db, user_id),
        "forecast": forecast,
        "activity": _activity(db, user_id),
        "weakest": [
            {"word": word_detail(words[c.word_id]), "card": s} for c, s in weakest
        ],
    }


def word_list(db: Session, user_id: str, search: str | None = None) -> list[dict]:
    now = eb.now_days()
    cards = {c.word_id: c for c in db.scalars(select(Card).where(Card.user_id == user_id))}
    query = select(Word).order_by(Word.lemma)
    if search:
        query = query.where(Word.lemma.ilike(f"%{search}%"))
    out = []
    for word in db.scalars(query):
        card = cards.get(word.id)
        summary = eb.card_summary(card, now) if card and card.reps > 0 else {
            "comfort": 0.0, "tier": "new", "depth": 0, "depth_name": "new",
            "recall_probability": None, "due": None, "reps": 0, "lapses": 0,
        }
        out.append({
            "id": word.id, "lemma": word.lemma, "pos": word.pos, "tier": word.tier, "set": word.set_no,
            "definition": word.definition, "cluster": word.cluster, "card": summary,
        })
    return out
