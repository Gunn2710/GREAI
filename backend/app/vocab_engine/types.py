"""Core types shared by the scheduler (FSRS) and the comfort model.

All timestamps are expressed in fractional days since the Unix epoch.
"""
from dataclasses import dataclass, field
from enum import IntEnum


class Rating(IntEnum):
    Again = 1
    Hard = 2
    Good = 3
    Easy = 4


class State(IntEnum):
    New = 0
    Learning = 1
    Review = 2
    Relearning = 3


class Mode(IntEnum):
    """Quiz modes. Each mode probes one level of the depth ladder."""

    Flashcard = 0  # level 1: recognize (self-rated)
    Meaning = 1    # level 1: recognize (pick the definition)
    Cloze = 2      # level 2: recall the word from context
    Synonyms = 3   # level 3: discriminate (pick the synonym pair)
    Usage = 4      # level 4: produce a sentence (AI graded)


class Confidence(IntEnum):
    None_ = 0  # trailing underscore: `None` is a Python keyword
    Guess = 1
    Unsure = 2
    Sure = 3


MAX_DEPTH = 4


@dataclass
class WordCard:
    """Per-user, per-word state. Mirrors the `cards` table one-to-one."""

    # Memory model (FSRS)
    state: State = State.New
    step: int = 0              # learning-step index while Learning
    stability: float = 0.0     # days until recall probability drops to 90%
    difficulty: float = 0.0    # 1 (easy) .. 10 (hard)
    due: float = 0.0
    last_review: float = 0.0
    reps: int = 0
    lapses: int = 0

    # Comfort model
    depth: int = 0                # highest depth-ladder level mastered (0..4)
    streak: int = 0               # consecutive spaced successes at the frontier level
    last_streak_at: float = 0.0   # when the streak last advanced
    calibration: float = 0.5      # EMA of "confidence matched the outcome"


@dataclass
class Evidence:
    """One observed interaction with a word."""

    mode: Mode = Mode.Meaning
    correct: bool = False
    response_ms: float = 0.0
    hint_used: bool = False
    confidence: Confidence = Confidence.None_
    self_rating: int = 0  # 1..4 for Flashcard mode, 0 otherwise


@dataclass
class SpeedStats:
    """Online mean/variance (Welford) of log response time for one mode."""

    n: float = 0.0
    mean: float = 0.0
    m2: float = 0.0


@dataclass
class SpeedBaselines:
    """A user's personal response-time baselines, indexed by Mode."""

    by_mode: list[SpeedStats] = field(default_factory=lambda: [SpeedStats() for _ in Mode])
