"""FSRS-5 memory model: stability, difficulty and retrievability per card,
plus learning steps and interval scheduling."""
import math
from dataclasses import dataclass, replace

from app.vocab_engine.types import Rating, State, WordCard

DECAY = -0.5
FACTOR = 19.0 / 81.0  # makes R(S, S) == 0.9
MINUTES_PER_DAY = 1440.0

# FSRS-5 default weights. Replace with per-user optimized weights once a user
# has enough review history.
DEFAULT_WEIGHTS = (
    0.40255, 1.18385, 3.173, 15.69105, 7.1949,
    0.5345, 1.4604, 0.0046, 1.54575, 0.1192,
    1.01925, 1.9395, 0.11, 0.29605, 2.2698,
    0.2315, 2.9898, 0.51655, 0.6621,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def _clamp_difficulty(d: float) -> float:
    return _clamp(d, 1.0, 10.0)


def _clamp_stability(s: float) -> float:
    return _clamp(s, 0.01, 36500.0)


@dataclass(frozen=True)
class FsrsParams:
    w: tuple[float, ...] = DEFAULT_WEIGHTS
    desired_retention: float = 0.9
    max_interval_days: float = 365.0
    # Learning steps in minutes (New/Learning) and relearning step (Relearning).
    again_step_min: float = 1.0
    hard_step_min: float = 6.0
    good_step_min: float = 10.0
    relearn_step_min: float = 10.0


class Fsrs:
    def __init__(self, params: FsrsParams | None = None):
        self.params = params or FsrsParams()

    @staticmethod
    def retrievability(elapsed_days: float, stability: float) -> float:
        """Probability of recall `elapsed_days` after the last review."""
        if stability <= 0.0:
            return 0.0
        elapsed_days = max(0.0, elapsed_days)
        return math.pow(1.0 + FACTOR * elapsed_days / stability, DECAY)

    def retrievability_at(self, card: WordCard, now: float) -> float:
        """Retrievability of a card at time `now` (1.0 for unseen cards)."""
        if card.state == State.New:
            return 1.0
        return self.retrievability(now - card.last_review, card.stability)

    def next_interval(self, stability: float) -> float:
        """Interval in days that hits the desired retention for a given stability."""
        p = self.params
        ivl = stability / FACTOR * (math.pow(p.desired_retention, 1.0 / DECAY) - 1.0)
        # Round half away from zero (C's round), not Python's banker's rounding.
        return _clamp(math.floor(ivl + 0.5), 1.0, p.max_interval_days)

    def _init_stability(self, r: Rating) -> float:
        return self.params.w[r - 1]

    def _init_difficulty(self, r: Rating) -> float:
        w = self.params.w
        return _clamp_difficulty(w[4] - math.exp(w[5] * (r - 1)) + 1.0)

    def _next_difficulty(self, d: float, r: Rating) -> float:
        w = self.params.w
        delta = -w[6] * (r - 3)
        damped = d + delta * (10.0 - d) / 9.0  # linear damping
        reverted = w[7] * self._init_difficulty(Rating.Easy) + (1.0 - w[7]) * damped
        return _clamp_difficulty(reverted)

    def _recall_stability(self, d: float, s: float, r: float, rating: Rating) -> float:
        w = self.params.w
        hard_penalty = w[15] if rating == Rating.Hard else 1.0
        easy_bonus = w[16] if rating == Rating.Easy else 1.0
        return s * (
            1.0
            + math.exp(w[8]) * (11.0 - d) * math.pow(s, -w[9])
            * (math.exp(w[10] * (1.0 - r)) - 1.0) * hard_penalty * easy_bonus
        )

    def _forget_stability(self, d: float, s: float, r: float) -> float:
        w = self.params.w
        sf = (
            w[11] * math.pow(d, -w[12])
            * (math.pow(s + 1.0, w[13]) - 1.0) * math.exp(w[14] * (1.0 - r))
        )
        return min(sf, s)

    def _short_term_stability(self, s: float, r: Rating) -> float:
        w = self.params.w
        return s * math.exp(w[17] * (r - 3 + w[18]))

    def review(self, card: WordCard, rating: Rating, now: float) -> WordCard:
        """Apply a rating at time `now`; returns the card with its memory state,
        state machine and due date updated (the input is left unchanged)."""
        c = replace(card)
        p = self.params

        # 1. Memory state.
        if c.state == State.New:
            c.stability = self._init_stability(rating)
            c.difficulty = self._init_difficulty(rating)
        else:
            elapsed = now - c.last_review
            old_d = c.difficulty
            if elapsed < 1.0:
                c.stability = self._short_term_stability(c.stability, rating)
            else:
                r = self.retrievability(elapsed, c.stability)
                if rating == Rating.Again:
                    c.stability = self._forget_stability(old_d, c.stability, r)
                else:
                    c.stability = self._recall_stability(old_d, c.stability, r, rating)
            c.difficulty = self._next_difficulty(old_d, rating)
        c.stability = _clamp_stability(c.stability)

        # 2. State machine and due date.
        def in_minutes(m: float) -> float:
            return now + m / MINUTES_PER_DAY

        def graduate() -> None:
            c.state = State.Review
            c.step = 0
            c.due = now + self.next_interval(c.stability)

        if c.state in (State.New, State.Learning):
            if rating == Rating.Again:
                c.state = State.Learning
                c.step = 0
                c.due = in_minutes(p.again_step_min)
            elif rating == Rating.Hard:
                c.state = State.Learning
                c.due = in_minutes(p.hard_step_min)
            elif rating == Rating.Good and c.step == 0:
                c.state = State.Learning
                c.step = 1
                c.due = in_minutes(p.good_step_min)
            else:
                graduate()
        elif c.state == State.Review:
            if rating == Rating.Again:
                c.lapses += 1
                c.state = State.Relearning
                c.due = in_minutes(p.relearn_step_min)
            else:
                graduate()
        elif c.state == State.Relearning:
            if rating == Rating.Again:
                c.due = in_minutes(p.relearn_step_min)
            else:
                graduate()

        c.reps += 1
        c.last_review = now
        return c
