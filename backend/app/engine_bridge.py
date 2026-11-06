"""Glue between database rows and the `vocab_engine` package.

The engine works in fractional days since the Unix epoch; the database stores
timezone-aware datetimes.
"""
from datetime import datetime, timezone

from app import vocab_engine as ve
from app.models import Card

SECONDS_PER_DAY = 86400.0

model = ve.ComfortModel()

MODE_BY_NAME = {
    "flashcard": ve.Mode.Flashcard,
    "meaning": ve.Mode.Meaning,
    "cloze": ve.Mode.Cloze,
    "synonyms": ve.Mode.Synonyms,
    "usage": ve.Mode.Usage,
}
NAME_BY_MODE = {v: k for k, v in MODE_BY_NAME.items()}

CONFIDENCE_BY_NAME = {
    None: ve.Confidence.None_,
    "guess": ve.Confidence.Guess,
    "unsure": ve.Confidence.Unsure,
    "sure": ve.Confidence.Sure,
}

TIER_NAMES = {
    ve.Tier.New: "new",
    ve.Tier.Learning: "learning",
    ve.Tier.Shaky: "shaky",
    ve.Tier.Comfortable: "comfortable",
    ve.Tier.Mastered: "mastered",
}

DEPTH_NAMES = ["new", "recognize", "recall", "discriminate", "use"]


def to_days(dt: datetime | None) -> float:
    if dt is None:
        return 0.0
    if dt.tzinfo is None:  # SQLite drops tzinfo; values are stored as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp() / SECONDS_PER_DAY


def from_days(days: float) -> datetime | None:
    if days <= 0:
        return None
    return datetime.fromtimestamp(days * SECONDS_PER_DAY, tz=timezone.utc)


def now_days() -> float:
    return to_days(datetime.now(timezone.utc))


def card_to_engine(row: Card) -> ve.WordCard:
    c = ve.WordCard()
    c.state = ve.State(row.state)
    c.step = row.step
    c.stability = row.stability
    c.difficulty = row.difficulty
    c.due = to_days(row.due)
    c.last_review = to_days(row.last_review)
    c.reps = row.reps
    c.lapses = row.lapses
    c.depth = row.depth
    c.streak = row.streak
    c.last_streak_at = to_days(row.last_streak_at)
    c.calibration = row.calibration
    return c


def apply_engine_card(row: Card, c: ve.WordCard) -> None:
    row.state = int(c.state)
    row.step = c.step
    row.stability = c.stability
    row.difficulty = c.difficulty
    row.due = from_days(c.due) or row.due
    row.last_review = from_days(c.last_review)
    row.reps = c.reps
    row.lapses = c.lapses
    row.depth = c.depth
    row.streak = c.streak
    row.last_streak_at = from_days(c.last_streak_at)
    row.calibration = c.calibration


def baselines_from_json(data: dict | None) -> ve.SpeedBaselines:
    b = ve.SpeedBaselines()
    for name, stats in (data or {}).items():
        mode = MODE_BY_NAME.get(name)
        if mode is None:
            continue
        s = ve.SpeedStats()
        s.n, s.mean, s.m2 = stats.get("n", 0.0), stats.get("mean", 0.0), stats.get("m2", 0.0)
        b.by_mode[mode] = s
    return b


def baselines_to_json(b: ve.SpeedBaselines) -> dict:
    out = {}
    for name, mode in MODE_BY_NAME.items():
        s = b.by_mode[mode]
        if s.n > 0:
            out[name] = {"n": s.n, "mean": s.mean, "m2": s.m2}
    return out


def card_summary(row: Card, now: float | None = None) -> dict:
    """Comfort numbers for display."""
    now = now_days() if now is None else now
    c = card_to_engine(row)
    return {
        "comfort": round(model.comfort(c, now), 1),
        "tier": TIER_NAMES[model.tier(c, now)],
        "depth": row.depth,
        "depth_name": DEPTH_NAMES[row.depth],
        "recall_probability": round(model.retrievability_at(c, now), 3),
        "stability_days": round(row.stability, 2),
        "due": row.due.isoformat() if row.due else None,
        "reps": row.reps,
        "lapses": row.lapses,
    }
