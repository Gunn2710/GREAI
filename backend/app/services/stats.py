"""Dashboard numbers: comfort tiers, depth ladder, due forecast, accuracy, streak."""
from collections import Counter
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import engine_bridge as eb
from app.models import Attempt, Card, Word, utcnow
from app.services.sets import word_sets
from app.services.study import get_profile, new_words_started_today, start_of_today, word_detail

TIERS = ["new", "learning", "shaky", "comfortable", "mastered"]
VOCAB_TYPES = ("flashcard", "meaning", "cloze", "synonyms", "usage")


def _as_utc(dt):
    return eb.from_days(eb.to_days(dt))


def _streak_days(db: Session, user_id: str) -> int:
    days = {
        _as_utc(dt).date()
        for dt in db.scalars(
            select(Attempt.created_at).where(
                Attempt.user_id == user_id, Attempt.created_at >= utcnow() - timedelta(days=400)
            )
        )
    }
    today = utcnow().date()
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


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

    since = now_dt - timedelta(days=30)
    recent = list(db.scalars(
        select(Attempt).where(
            Attempt.user_id == user_id, Attempt.created_at >= since,
            Attempt.item_type.in_(VOCAB_TYPES),
        )
    ))
    accuracy = round(sum(a.correct for a in recent) / len(recent), 3) if recent else None
    reviews_today = sum(1 for a in recent if _as_utc(a.created_at) >= start_of_today())

    weakest = sorted(
        (x for x in summaries if x[0].reps > 0), key=lambda x: x[1]["comfort"]
    )[:5]
    new_left = max(0, min(profile.daily_new_words - new_words_started_today(db, user_id),
                          total_words - len(cards)))

    sets = word_sets(db, user_id)
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
        "weakest": [
            {"word": word_detail(db.get(Word, c.word_id)), "card": s} for c, s in weakest
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
