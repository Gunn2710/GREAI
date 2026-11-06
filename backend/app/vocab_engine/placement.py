"""Placement test: estimate a user's vocabulary level (theta) from a short set
of answers, using a one-parameter IRT model with a guessing floor.

theta and word difficulty b share one scale: a user with theta == b knows the
word with probability 0.5.
"""
import math
from dataclasses import dataclass

GRID_MIN = -4.0
GRID_MAX = 4.0
GRID_POINTS = 161


@dataclass
class IrtResponse:
    difficulty: float = 0.0  # b
    correct: bool = False


@dataclass
class AbilityEstimate:
    theta: float = 0.0
    se: float = 1.0  # posterior standard deviation


def p_know(theta: float, b: float) -> float:
    """Probability the user actually knows a word (no guessing)."""
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def p_correct(theta: float, b: float, guess: float = 0.2) -> float:
    """Probability of answering a multiple-choice item correctly: knows it, or
    doesn't and guesses right with probability `guess`."""
    return guess + (1.0 - guess) * p_know(theta, b)


def estimate_ability(
    responses: list[IrtResponse],
    guess: float = 0.2,
    prior_mean: float = 0.0,
    prior_sd: float = 1.0,
) -> AbilityEstimate:
    """Expected a posteriori estimate on a grid, with a Normal(prior_mean, prior_sd) prior."""
    # Work in log space so long response lists don't underflow.
    thetas, logw = [], []
    for i in range(GRID_POINTS):
        t = GRID_MIN + (GRID_MAX - GRID_MIN) * i / (GRID_POINTS - 1)
        z = (t - prior_mean) / prior_sd
        lw = -0.5 * z * z
        for r in responses:
            p = min(max(p_correct(t, r.difficulty, guess), 1e-9), 1.0 - 1e-9)
            lw += math.log(p) if r.correct else math.log(1.0 - p)
        thetas.append(t)
        logw.append(lw)

    max_logw = max(logw)
    w = [math.exp(lw - max_logw) for lw in logw]
    total = 0.0
    mean = 0.0
    for wi, t in zip(w, thetas):
        total += wi
        mean += wi * t
    mean /= total
    var = 0.0
    for wi, t in zip(w, thetas):
        var += wi * (t - mean) * (t - mean)
    return AbilityEstimate(theta=mean, se=math.sqrt(var / total))


def update_difficulty(b: float, theta: float, correct: bool, guess: float = 0.2, k: float = 0.05) -> float:
    """Elo-style nudge to a word's difficulty after one answer from a user of
    ability theta: harder if they missed it, easier if they got it."""
    expected = p_correct(theta, b, guess)
    return b + k * (expected - (1.0 if correct else 0.0))


def update_ability(theta: float, b: float, correct: bool, guess: float = 0.2, k: float = 0.3) -> float:
    """The matching nudge to a user's ability after answering an item of difficulty b."""
    expected = p_correct(theta, b, guess)
    return theta + k * ((1.0 if correct else 0.0) - expected)
