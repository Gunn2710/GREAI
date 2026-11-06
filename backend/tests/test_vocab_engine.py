"""Unit tests for the scheduling, comfort and placement math (no database)."""
from dataclasses import replace

import pytest

from app.vocab_engine import (
    ComfortModel,
    Confidence,
    Evidence,
    Fsrs,
    IrtResponse,
    Mode,
    Rating,
    SpeedBaselines,
    State,
    Tier,
    WordCard,
    estimate_ability,
    p_correct,
    p_know,
    update_ability,
    update_difficulty,
)

MINUTE = 1.0 / 1440.0


def test_retrievability():
    assert Fsrs.retrievability(10.0, 10.0) == pytest.approx(0.9, abs=1e-9)
    assert Fsrs.retrievability(0.0, 5.0) == 1.0
    assert Fsrs.retrievability(30.0, 5.0) < Fsrs.retrievability(10.0, 5.0)


def test_learning_steps_and_graduation():
    f = Fsrs()
    now = 20000.0
    c = f.review(WordCard(), Rating.Good, now)
    assert c.state == State.Learning
    assert c.step == 1
    assert c.due == pytest.approx(now + 10 * MINUTE, abs=1e-9)

    now = c.due
    c = f.review(c, Rating.Good, now)
    assert c.state == State.Review
    assert c.due - now >= 1.0

    now = c.due + 1.0
    s_before = c.stability
    c = f.review(c, Rating.Good, now)
    assert c.stability > s_before

    now = c.due
    c = f.review(c, Rating.Again, now)
    assert c.state == State.Relearning
    assert c.lapses == 1


def test_review_leaves_input_unchanged():
    card = WordCard()
    Fsrs().review(card, Rating.Good, 100.0)
    assert card == WordCard()


def test_easy_beats_good():
    f = Fsrs()
    g = f.review(WordCard(), Rating.Good, 0.0)
    e = f.review(WordCard(), Rating.Easy, 0.0)
    assert e.stability > g.stability
    assert e.difficulty < g.difficulty


def test_implicit_rating():
    m = ComfortModel()
    b = SpeedBaselines()
    ev = Evidence(mode=Mode.Meaning, correct=False)
    assert m.implicit_rating(ev, b) == Rating.Again

    ev.correct = True
    assert m.implicit_rating(ev, b) == Rating.Good
    ev.hint_used = True
    assert m.implicit_rating(ev, b) == Rating.Hard
    ev.hint_used = False
    ev.confidence = Confidence.Guess
    assert m.implicit_rating(ev, b) == Rating.Hard

    # Build a personal baseline around ~4s, then answer much slower/faster.
    for i in range(20):
        s = Evidence(mode=Mode.Meaning, correct=True, response_ms=3500.0 + (i % 5) * 250.0)
        b = m.process(WordCard(), s, b, 0.0).baselines
    ev.confidence = Confidence.Sure
    ev.response_ms = 15000.0
    assert m.implicit_rating(ev, b) == Rating.Hard
    ev.response_ms = 1500.0
    assert m.implicit_rating(ev, b) == Rating.Easy

    fc = Evidence(mode=Mode.Flashcard, correct=True, self_rating=4, confidence=Confidence.Guess)
    assert m.implicit_rating(fc, b) == Rating.Hard


def test_process_leaves_baselines_unchanged():
    m = ComfortModel()
    b = SpeedBaselines()
    out = m.process(WordCard(), Evidence(correct=True, response_ms=4000.0), b, 0.0)
    assert out.baselines.by_mode[Mode.Meaning].n == 1.0
    assert b.by_mode[Mode.Meaning].n == 0.0


def test_depth_ladder():
    m = ComfortModel()
    b = SpeedBaselines()
    now = 100.0
    ev = Evidence(mode=Mode.Meaning, correct=True, confidence=Confidence.Sure)

    r = m.process(WordCard(), ev, b, now)
    assert r.card.depth == 0 and r.card.streak == 1
    # A second success within the spacing window does not count.
    r = m.process(r.card, ev, b, now + 0.01)
    assert r.card.depth == 0 and r.card.streak == 1
    r = m.process(r.card, ev, b, now + 1.0)
    assert r.promoted and r.card.depth == 1

    # Cloze is now the frontier; succeed twice spaced apart -> depth 2.
    ev.mode = Mode.Cloze
    r = m.process(r.card, ev, b, now + 3.0)
    r = m.process(r.card, ev, b, now + 6.0)
    assert r.card.depth == 2

    # Failing recognition drops below level 1.
    ev.mode = Mode.Meaning
    ev.correct = False
    calib_before = r.card.calibration
    r = m.process(r.card, ev, b, now + 10.0)
    assert r.demoted and r.card.depth == 0
    # Sure + wrong drags calibration down.
    assert r.card.calibration < calib_before


def test_comfort_and_modes():
    m = ComfortModel()
    fresh = WordCard()
    assert m.comfort(fresh, 0.0) == 0.0
    assert m.tier(fresh, 0.0) == Tier.New
    assert m.choose_mode(fresh, 0.5, True) == Mode.Flashcard

    strong = WordCard(
        state=State.Review, reps=10, stability=120.0, difficulty=3.0,
        last_review=0.0, depth=4, calibration=1.0,
    )
    assert m.tier(strong, 1.0) == Tier.Mastered
    # Long after the last review, comfort decays.
    assert m.comfort(strong, 400.0) < m.comfort(strong, 1.0)

    mid = replace(strong, depth=1)
    assert m.choose_mode(mid, 0.1, True) == Mode.Cloze    # frontier
    assert m.choose_mode(mid, 0.9, True) == Mode.Meaning  # maintenance
    mid.depth = 2
    assert m.choose_mode(mid, 0.1, False) == Mode.Synonyms  # frontier
    mid.depth = 3
    assert m.choose_mode(mid, 0.1, False) != Mode.Usage  # usage disabled


def test_learning_cards_capped_below_shaky():
    m = ComfortModel()
    c = Fsrs().review(WordCard(), Rating.Good, 0.0)
    assert c.state == State.Learning
    assert m.comfort(c, 0.0) <= 39.0
    assert m.tier(c, 0.0) == Tier.Learning


def test_placement():
    assert p_know(1.0, 1.0) == pytest.approx(0.5, abs=1e-12)
    assert p_correct(-10.0, 0.0, 0.25) == pytest.approx(0.25, abs=1e-3)

    # No answers: the estimate is the prior.
    prior = estimate_ability([])
    assert abs(prior.theta) < 1e-6
    assert prior.se == pytest.approx(1.0, abs=0.02)

    # Simulate a strong user: right on everything up to b = 1.5, wrong above.
    bs = [-1.0 + 0.25 * i for i in range(15)]
    strong = estimate_ability([IrtResponse(b, b <= 1.5) for b in bs])
    weak = estimate_ability([IrtResponse(b, b <= -0.5) for b in bs])
    assert strong.theta > 0.8
    assert weak.theta < 0.0
    assert strong.theta > weak.theta
    assert strong.se < 1.0

    # Missing a word makes it look harder; getting it right, easier.
    assert update_difficulty(0.0, 0.0, False) > 0.0
    assert update_difficulty(0.0, 0.0, True) < 0.0
    assert update_ability(0.0, 0.0, True) > 0.0
    assert update_ability(0.0, 0.0, False) < 0.0
    # Missing a much harder item barely moves the estimate.
    assert abs(update_ability(0.0, 3.0, False)) < abs(update_ability(0.0, 0.0, False))
