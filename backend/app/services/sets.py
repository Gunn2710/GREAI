"""Study sets: GregMat's groups of 30 in order, then the rest of the bank in
groups of 20-30, most common first (see app/seed/seed.py assign_sets).

New words come from the current set (the first one with words not started
yet), so the sets are a progression. Progress per set:
    started   words the user has begun (studied, or placed / fast-tracked)
    learned   words at Comfortable or Mastered
    status    "done" (all learned), "reviewing" (all started), "current",
              or "locked" (later sets: no new words from them yet)
    source    "gregmat" for a set made from one of GregMat's groups, else "bank"
"""
from collections import defaultdict
from functools import cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import engine_bridge as eb
from app.models import Card, Word
from app.seed.seed import load_groups

LEARNED_TIERS = ("comfortable", "mastered")


@cache
def _grouped() -> frozenset[str]:
    return frozenset(lemma for group in load_groups() for lemma in group)


def word_sets(db: Session, user_id: str) -> dict:
    now = eb.now_days()
    cards = {c.word_id: c for c in db.scalars(select(Card).where(Card.user_id == user_id))}
    sets: dict[int, dict] = defaultdict(lambda: {"size": 0, "started": 0, "learned": 0, "tier": 1, "source": "bank"})
    grouped = _grouped()
    for word_id, lemma, set_no, tier in db.execute(
        select(Word.id, Word.lemma, Word.set_no, Word.tier).where(Word.set_no.is_not(None))
    ):
        s = sets[set_no]
        s["size"] += 1
        s["tier"] = tier
        if lemma in grouped:
            s["source"] = "gregmat"
        card = cards.get(word_id)
        if card is not None:
            s["started"] += 1
            if card.reps > 0 and eb.card_summary(card, now)["tier"] in LEARNED_TIERS:
                s["learned"] += 1

    current = next((n for n in sorted(sets) if sets[n]["started"] < sets[n]["size"]), None)
    out = []
    for n in sorted(sets):
        s = sets[n]
        if s["learned"] == s["size"]:
            status = "done"
        elif s["started"] == s["size"]:
            status = "reviewing"
        else:
            status = "current" if n == current else "locked"
        out.append({"number": n, **s, "status": status})
    return {"sets": out, "current": current}


def current_set(db: Session, user_id: str) -> dict | None:
    """The set new words are coming from, with the number of sets in all."""
    data = word_sets(db, user_id)
    s = next((s for s in data["sets"] if s["number"] == data["current"]), None)
    return {**s, "total": len(data["sets"])} if s else None
