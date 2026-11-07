"""Word difficulty on the same scale as user ability (theta), and cards for
words a user very likely already knows."""
from datetime import timedelta

from app import vocab_engine as ve
from app.models import Card, Word, utcnow

# Starting difficulty by frequency tier; Word.global_difficulty is a learned
# offset on top, updated from placement answers.
TIER_PRIOR = {1: 0.0, 2: 0.7, 3: 1.5}

# Predicted-known probability above which a new word skips the learning steps.
# A wrong fast-track costs one recall question (a miss sends the word to
# relearning), and placement tends to underestimate strong users, so this
# leans permissive.
FAST_TRACK_P = 0.75


def tier_prior(word: Word) -> float:
    return TIER_PRIOR.get(word.tier, 0.7)


def word_difficulty(word: Word) -> float:
    return tier_prior(word) + (word.global_difficulty or 0.0)


def known_card(user_id: str, word_id: int, origin: str, due_in_days: float) -> Card:
    """A card that skips the learning steps and starts at the recognize level;
    its first review checks recall, and a miss sends it back to relearning."""
    now = utcnow()
    return Card(
        user_id=user_id, word_id=word_id, origin=origin,
        state=int(ve.State.Review), reps=1, stability=4.0, difficulty=4.5,
        depth=1, calibration=0.6, last_review=now, due=now + timedelta(days=due_in_days),
    )
