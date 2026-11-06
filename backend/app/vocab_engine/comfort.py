"""Comfort model: turns raw interactions into FSRS ratings, moves words along
the depth ladder, tracks confidence calibration and personal speed, and
combines everything into a 0-100 comfort score."""
import math
from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import IntEnum

from app.vocab_engine.fsrs import Fsrs, FsrsParams, _clamp
from app.vocab_engine.types import (
    MAX_DEPTH,
    Confidence,
    Evidence,
    Mode,
    Rating,
    SpeedBaselines,
    State,
    WordCard,
)

MIN_MS = 300.0
MAX_MS = 120000.0


class Tier(IntEnum):
    New = 0
    Learning = 1
    Shaky = 2
    Comfortable = 3
    Mastered = 4


@dataclass(frozen=True)
class ComfortParams:
    # Comfort score weights (sum to 1).
    w_retrievability: float = 0.45
    w_depth: float = 0.30
    w_stability: float = 0.15
    w_calibration: float = 0.10
    stability_target_days: float = 60.0

    # Depth ladder.
    promote_after: int = 2              # spaced successes needed to climb a level
    streak_spacing_days: float = 0.25   # successes closer than this count once

    # Implicit grading from response time (z-score of log ms vs. personal baseline).
    slow_z: float = 1.0
    fast_z: float = -0.5
    min_samples_for_speed: float = 5.0

    calibration_alpha: float = 0.3

    # Mode selection: share of items at the frontier level (rest is maintenance).
    frontier_share: float = 0.7


@dataclass
class ReviewOutcome:
    card: WordCard
    baselines: SpeedBaselines
    rating: Rating = Rating.Good
    promoted: bool = False
    demoted: bool = False
    comfort_before: float = 0.0
    comfort_after: float = 0.0


_MODE_LEVEL = {
    Mode.Flashcard: 1,
    Mode.Meaning: 1,
    Mode.Cloze: 2,
    Mode.Synonyms: 3,
    Mode.Usage: 4,
}
_MODE_FOR_LEVEL = {1: Mode.Meaning, 2: Mode.Cloze, 3: Mode.Synonyms, 4: Mode.Usage}

# (target when correct, target when wrong) for each declared confidence.
_CALIBRATION_TARGETS = {
    Confidence.Sure: (1.0, 0.0),
    Confidence.Unsure: (0.7, 0.3),
    Confidence.Guess: (0.4, 0.3),
}


def mode_level(mode: Mode) -> int:
    return _MODE_LEVEL.get(mode, 1)


def _log_ms(ms: float) -> float:
    return math.log(_clamp(ms, MIN_MS, MAX_MS))


class ComfortModel:
    def __init__(self, fsrs: FsrsParams | None = None, params: ComfortParams | None = None):
        self.fsrs = Fsrs(fsrs)
        self.params = params or ComfortParams()

    def speed_z(self, ev: Evidence, b: SpeedBaselines) -> float:
        """Response-time z-score against the user's own baseline for this mode
        (0 if there is not enough data yet)."""
        s = b.by_mode[ev.mode]
        if s.n < self.params.min_samples_for_speed or ev.response_ms <= 0.0:
            return 0.0
        var = s.m2 / (s.n - 1.0)
        sd = math.sqrt(max(var, 1e-6))
        return (_log_ms(ev.response_ms) - s.mean) / sd

    def implicit_rating(self, ev: Evidence, b: SpeedBaselines) -> Rating:
        """Map evidence to an FSRS rating without the user rating themselves."""
        if not ev.correct:
            return Rating.Again

        # Flashcards are self-rated; only a declared guess can pull the rating down.
        if ev.mode == Mode.Flashcard and 1 <= ev.self_rating <= 4:
            r = Rating(ev.self_rating)
            return min(r, Rating.Hard) if ev.confidence == Confidence.Guess else r

        if ev.hint_used or ev.confidence == Confidence.Guess:
            return Rating.Hard

        z = self.speed_z(ev, b)
        if z > self.params.slow_z:
            return Rating.Hard

        fast = z < self.params.fast_z
        sure = ev.confidence == Confidence.Sure
        # Harder modes are stronger evidence: a quick, confident answer at the
        # discriminate/use levels earns Easy.
        if fast and sure:
            return Rating.Easy
        if mode_level(ev.mode) >= 3 and sure and z < 0.0:
            return Rating.Easy
        return Rating.Good

    @staticmethod
    def _update_speed(b: SpeedBaselines, ev: Evidence) -> None:
        if ev.response_ms <= 0.0:
            return
        s = b.by_mode[ev.mode]
        x = _log_ms(ev.response_ms)
        s.n += 1.0
        delta = x - s.mean
        s.mean += delta / s.n
        s.m2 += delta * (x - s.mean)

    def _update_depth(self, c: WordCard, ev: Evidence, rating: Rating, now: float) -> tuple[bool, bool]:
        """Returns (promoted, demoted)."""
        level = mode_level(ev.mode)
        frontier = min(c.depth + 1, MAX_DEPTH)

        if rating == Rating.Again:
            demoted = False
            if level <= c.depth:
                # Failed a level already "mastered": drop below it.
                c.depth = max(0, min(c.depth - 1, level - 1))
                demoted = True
            c.streak = 0
            return False, demoted

        if level != frontier or c.depth >= MAX_DEPTH:
            return False, False
        # A self-rated "Hard" flashcard is not evidence of mastery.
        if rating == Rating.Hard and ev.mode == Mode.Flashcard:
            return False, False

        spaced = c.streak == 0 or (now - c.last_streak_at) >= self.params.streak_spacing_days
        if not spaced:
            return False, False

        c.streak += 1
        c.last_streak_at = now
        if c.streak >= self.params.promote_after:
            c.depth = min(c.depth + 1, MAX_DEPTH)
            c.streak = 0
            return True, False
        return False, False

    def _update_calibration(self, c: WordCard, ev: Evidence) -> None:
        targets = _CALIBRATION_TARGETS.get(ev.confidence)
        if targets is None:
            return
        target = targets[0] if ev.correct else targets[1]
        c.calibration += self.params.calibration_alpha * (target - c.calibration)

    def comfort(self, c: WordCard, now: float) -> float:
        if c.state == State.New and c.reps == 0:
            return 0.0
        p = self.params
        r = self.fsrs.retrievability_at(c, now)
        depth = c.depth / MAX_DEPTH
        stab = min(1.0, math.log1p(c.stability) / math.log1p(p.stability_target_days))
        score = (
            p.w_retrievability * r + p.w_depth * depth
            + p.w_stability * stab + p.w_calibration * c.calibration
        )
        score = _clamp(100.0 * score, 0.0, 100.0)
        # Right after a review R is ~1 even for a word seen once; words still in
        # learning steps stay in the Learning tier until they graduate.
        if c.state in (State.Learning, State.Relearning):
            score = min(score, 39.0)
        return score

    def tier(self, c: WordCard, now: float) -> Tier:
        if c.state == State.New and c.reps == 0:
            return Tier.New
        s = self.comfort(c, now)
        if s >= 85.0:
            return Tier.Mastered
        if s >= 65.0:
            return Tier.Comfortable
        if s >= 40.0:
            return Tier.Shaky
        return Tier.Learning

    def priority(self, c: WordCard, now: float) -> float:
        """Higher means "show this sooner" among cards that are already due."""
        r = self.fsrs.retrievability_at(c, now)
        p = (1.0 - r) + 0.3 * (1.0 - c.calibration)
        if c.state in (State.Learning, State.Relearning):
            p += 0.5
        overdue_days = max(0.0, now - c.due)
        p += min(0.5, overdue_days / 30.0)
        return p

    def choose_mode(self, c: WordCard, u: float, allow_usage: bool) -> Mode:
        """Pick a quiz mode for a card. `u` is a uniform random number in [0, 1)."""
        # Brand-new or still in learning steps: introduce/reinforce with recognition.
        if c.reps == 0:
            return Mode.Flashcard
        if c.state in (State.Learning, State.Relearning):
            return Mode.Flashcard if u < 0.5 else Mode.Meaning

        max_level = MAX_DEPTH if allow_usage else MAX_DEPTH - 1
        frontier = min(c.depth + 1, max_level)
        level = frontier
        if c.depth >= max_level:
            # Fully mastered: keep it fresh with an even mix of every level.
            level = _clamp(1 + int(u * max_level), 1, max_level)
        elif u >= self.params.frontier_share and frontier > 1:
            # Maintenance: spread the remaining probability over lower levels.
            v = (u - self.params.frontier_share) / (1.0 - self.params.frontier_share)
            level = _clamp(1 + int(v * (frontier - 1)), 1, frontier - 1)
        return _MODE_FOR_LEVEL[level]

    def retrievability_at(self, c: WordCard, now: float) -> float:
        return self.fsrs.retrievability_at(c, now)

    def process(self, card: WordCard, ev: Evidence, baselines: SpeedBaselines, now: float) -> ReviewOutcome:
        """Full update for one interaction: grade, schedule, ladder, calibration,
        speed. Inputs are left unchanged."""
        comfort_before = self.comfort(card, now)
        rating = self.implicit_rating(ev, baselines)

        c = self.fsrs.review(card, rating, now)
        promoted, demoted = self._update_depth(c, ev, rating, now)
        self._update_calibration(c, ev)

        new_baselines = deepcopy(baselines)
        self._update_speed(new_baselines, ev)

        return ReviewOutcome(
            card=c,
            baselines=new_baselines,
            rating=rating,
            promoted=promoted,
            demoted=demoted,
            comfort_before=comfort_before,
            comfort_after=self.comfort(c, now),
        )
