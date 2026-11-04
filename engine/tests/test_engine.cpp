// Minimal dependency-free tests for the engine. Run with `make test`.
#include <cmath>
#include <cstdio>
#include <cstdlib>

#include "vocab_engine/comfort.hpp"
#include "vocab_engine/fsrs.hpp"
#include "vocab_engine/placement.hpp"

using namespace vocab;

static int failures = 0;
#define CHECK(cond)                                                    \
    do {                                                               \
        if (!(cond)) {                                                 \
            std::fprintf(stderr, "FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
            ++failures;                                                \
        }                                                              \
    } while (0)

constexpr double kMin = 1.0 / 1440.0;

static void test_retrievability() {
    CHECK(std::fabs(Fsrs::retrievability(10.0, 10.0) - 0.9) < 1e-9);
    CHECK(Fsrs::retrievability(0.0, 5.0) == 1.0);
    CHECK(Fsrs::retrievability(30.0, 5.0) < Fsrs::retrievability(10.0, 5.0));
}

static void test_learning_steps_and_graduation() {
    Fsrs f;
    WordCard c;
    double now = 20000.0;
    c = f.review(c, Rating::Good, now);
    CHECK(c.state == State::Learning);
    CHECK(c.step == 1);
    CHECK(std::fabs(c.due - (now + 10 * kMin)) < 1e-9);

    now = c.due;
    c = f.review(c, Rating::Good, now);
    CHECK(c.state == State::Review);
    CHECK(c.due - now >= 1.0);

    now = c.due + 1.0;
    double s_before = c.stability;
    c = f.review(c, Rating::Good, now);
    CHECK(c.stability > s_before);

    now = c.due;
    c = f.review(c, Rating::Again, now);
    CHECK(c.state == State::Relearning);
    CHECK(c.lapses == 1);
}

static void test_easy_beats_good() {
    Fsrs f;
    WordCard base;
    WordCard g = f.review(base, Rating::Good, 0.0);
    WordCard e = f.review(base, Rating::Easy, 0.0);
    CHECK(e.stability > g.stability);
    CHECK(e.difficulty < g.difficulty);
}

static void test_implicit_rating() {
    ComfortModel m;
    SpeedBaselines b;
    Evidence ev;
    ev.mode = Mode::Meaning;
    ev.correct = false;
    CHECK(m.implicit_rating(ev, b) == Rating::Again);

    ev.correct = true;
    CHECK(m.implicit_rating(ev, b) == Rating::Good);
    ev.hint_used = true;
    CHECK(m.implicit_rating(ev, b) == Rating::Hard);
    ev.hint_used = false;
    ev.confidence = Confidence::Guess;
    CHECK(m.implicit_rating(ev, b) == Rating::Hard);

    // Build a personal baseline around ~4s, then answer much slower/faster.
    for (int i = 0; i < 20; ++i) {
        Evidence s;
        s.mode = Mode::Meaning;
        s.correct = true;
        s.response_ms = 3500.0 + (i % 5) * 250.0;
        b = m.process(WordCard{}, s, b, 0.0).baselines;
    }
    ev.confidence = Confidence::Sure;
    ev.response_ms = 15000.0;
    CHECK(m.implicit_rating(ev, b) == Rating::Hard);
    ev.response_ms = 1500.0;
    CHECK(m.implicit_rating(ev, b) == Rating::Easy);

    Evidence fc;
    fc.mode = Mode::Flashcard;
    fc.correct = true;
    fc.self_rating = 4;
    fc.confidence = Confidence::Guess;
    CHECK(m.implicit_rating(fc, b) == Rating::Hard);
}

static void test_depth_ladder() {
    ComfortModel m;
    SpeedBaselines b;
    WordCard c;
    double now = 100.0;

    Evidence ev;
    ev.mode = Mode::Meaning;
    ev.correct = true;
    ev.confidence = Confidence::Sure;

    auto r = m.process(c, ev, b, now);
    CHECK(r.card.depth == 0 && r.card.streak == 1);
    // A second success within the spacing window does not count.
    r = m.process(r.card, ev, b, now + 0.01);
    CHECK(r.card.depth == 0 && r.card.streak == 1);
    r = m.process(r.card, ev, b, now + 1.0);
    CHECK(r.promoted && r.card.depth == 1);

    // Cloze is now the frontier; succeed twice spaced apart -> depth 2.
    ev.mode = Mode::Cloze;
    r = m.process(r.card, ev, b, now + 3.0);
    r = m.process(r.card, ev, b, now + 6.0);
    CHECK(r.card.depth == 2);

    // Failing recognition drops below level 1.
    ev.mode = Mode::Meaning;
    ev.correct = false;
    double calib_before = r.card.calibration;
    r = m.process(r.card, ev, b, now + 10.0);
    CHECK(r.demoted && r.card.depth == 0);
    // Sure + wrong drags calibration down.
    CHECK(r.card.calibration < calib_before);
}

static void test_comfort_and_modes() {
    ComfortModel m;
    WordCard fresh;
    CHECK(m.comfort(fresh, 0.0) == 0.0);
    CHECK(m.tier(fresh, 0.0) == Tier::New);
    CHECK(m.choose_mode(fresh, 0.5, true) == Mode::Flashcard);

    WordCard strong;
    strong.state = State::Review;
    strong.reps = 10;
    strong.stability = 120.0;
    strong.difficulty = 3.0;
    strong.last_review = 0.0;
    strong.depth = 4;
    strong.calibration = 1.0;
    CHECK(m.tier(strong, 1.0) == Tier::Mastered);
    // Long after the last review, comfort decays.
    CHECK(m.comfort(strong, 400.0) < m.comfort(strong, 1.0));

    WordCard mid = strong;
    mid.depth = 1;
    CHECK(m.choose_mode(mid, 0.1, true) == Mode::Cloze);    // frontier
    CHECK(m.choose_mode(mid, 0.9, true) == Mode::Meaning);  // maintenance
    mid.depth = 2;
    CHECK(m.choose_mode(mid, 0.1, false) == Mode::Synonyms);  // frontier
    mid.depth = 3;
    CHECK(m.choose_mode(mid, 0.1, false) != Mode::Usage);  // usage disabled
}

static void test_placement() {
    CHECK(std::fabs(p_know(1.0, 1.0) - 0.5) < 1e-12);
    CHECK(std::fabs(p_correct(-10.0, 0.0, 0.25) - 0.25) < 1e-3);

    // No answers: the estimate is the prior.
    AbilityEstimate prior = estimate_ability({});
    CHECK(std::fabs(prior.theta) < 1e-6);
    CHECK(std::fabs(prior.se - 1.0) < 0.02);

    // Simulate a strong user: right on everything up to b = 1.5, wrong above.
    std::vector<IrtResponse> strong, weak;
    for (double b = -1.0; b <= 2.5; b += 0.25) {
        strong.push_back({b, b <= 1.5});
        weak.push_back({b, b <= -0.5});
    }
    AbilityEstimate s = estimate_ability(strong);
    AbilityEstimate w = estimate_ability(weak);
    CHECK(s.theta > 0.8);
    CHECK(w.theta < 0.0);
    CHECK(s.theta > w.theta);
    CHECK(s.se < 1.0);

    // Missing a word makes it look harder; getting it right, easier.
    CHECK(update_difficulty(0.0, 0.0, false) > 0.0);
    CHECK(update_difficulty(0.0, 0.0, true) < 0.0);
    CHECK(update_ability(0.0, 0.0, true) > 0.0);
    CHECK(update_ability(0.0, 0.0, false) < 0.0);
    // Missing a much harder item barely moves the estimate.
    CHECK(std::fabs(update_ability(0.0, 3.0, false)) < std::fabs(update_ability(0.0, 0.0, false)));
}

int main() {
    test_retrievability();
    test_learning_steps_and_graduation();
    test_easy_beats_good();
    test_implicit_rating();
    test_depth_ladder();
    test_comfort_and_modes();
    test_placement();
    if (failures) {
        std::fprintf(stderr, "%d check(s) failed\n", failures);
        return EXIT_FAILURE;
    }
    std::puts("engine tests passed");
    return EXIT_SUCCESS;
}
