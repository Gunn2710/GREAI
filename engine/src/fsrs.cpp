#include "vocab_engine/fsrs.hpp"

#include <algorithm>
#include <cmath>

namespace vocab {

namespace {
constexpr double kDecay = -0.5;
constexpr double kFactor = 19.0 / 81.0;  // makes R(S, S) == 0.9
constexpr double kMinutesPerDay = 1440.0;

double clamp_difficulty(double d) { return std::clamp(d, 1.0, 10.0); }
double clamp_stability(double s) { return std::clamp(s, 0.01, 36500.0); }
int g(Rating r) { return static_cast<int>(r); }
}  // namespace

double Fsrs::retrievability(double elapsed_days, double stability) {
    if (stability <= 0.0) return 0.0;
    elapsed_days = std::max(0.0, elapsed_days);
    return std::pow(1.0 + kFactor * elapsed_days / stability, kDecay);
}

double Fsrs::retrievability_at(const WordCard& card, double now) const {
    if (card.state == State::New) return 1.0;
    return retrievability(now - card.last_review, card.stability);
}

double Fsrs::next_interval(double stability) const {
    double ivl = stability / kFactor *
                 (std::pow(p_.desired_retention, 1.0 / kDecay) - 1.0);
    return std::clamp(std::round(ivl), 1.0, p_.max_interval_days);
}

double Fsrs::init_stability(Rating r) const { return p_.w[g(r) - 1]; }

double Fsrs::init_difficulty(Rating r) const {
    return clamp_difficulty(p_.w[4] - std::exp(p_.w[5] * (g(r) - 1)) + 1.0);
}

double Fsrs::next_difficulty(double d, Rating r) const {
    double delta = -p_.w[6] * (g(r) - 3);
    double damped = d + delta * (10.0 - d) / 9.0;  // linear damping
    double reverted = p_.w[7] * init_difficulty(Rating::Easy) + (1.0 - p_.w[7]) * damped;
    return clamp_difficulty(reverted);
}

double Fsrs::recall_stability(double d, double s, double r, Rating rating) const {
    double hard_penalty = rating == Rating::Hard ? p_.w[15] : 1.0;
    double easy_bonus = rating == Rating::Easy ? p_.w[16] : 1.0;
    return s * (1.0 + std::exp(p_.w[8]) * (11.0 - d) * std::pow(s, -p_.w[9]) *
                          (std::exp(p_.w[10] * (1.0 - r)) - 1.0) * hard_penalty *
                          easy_bonus);
}

double Fsrs::forget_stability(double d, double s, double r) const {
    double sf = p_.w[11] * std::pow(d, -p_.w[12]) *
                (std::pow(s + 1.0, p_.w[13]) - 1.0) * std::exp(p_.w[14] * (1.0 - r));
    return std::min(sf, s);
}

double Fsrs::short_term_stability(double s, Rating r) const {
    return s * std::exp(p_.w[17] * (g(r) - 3 + p_.w[18]));
}

WordCard Fsrs::review(WordCard c, Rating rating, double now) const {
    // 1. Memory state.
    if (c.state == State::New) {
        c.stability = init_stability(rating);
        c.difficulty = init_difficulty(rating);
    } else {
        double elapsed = now - c.last_review;
        double old_d = c.difficulty;
        if (elapsed < 1.0) {
            c.stability = short_term_stability(c.stability, rating);
        } else {
            double r = retrievability(elapsed, c.stability);
            c.stability = rating == Rating::Again
                              ? forget_stability(old_d, c.stability, r)
                              : recall_stability(old_d, c.stability, r, rating);
        }
        c.difficulty = next_difficulty(old_d, rating);
    }
    c.stability = clamp_stability(c.stability);

    // 2. State machine and due date.
    auto in_minutes = [now](double m) { return now + m / kMinutesPerDay; };
    auto graduate = [&]() {
        c.state = State::Review;
        c.step = 0;
        c.due = now + next_interval(c.stability);
    };

    switch (c.state) {
        case State::New:
        case State::Learning:
            if (rating == Rating::Again) {
                c.state = State::Learning;
                c.step = 0;
                c.due = in_minutes(p_.again_step_min);
            } else if (rating == Rating::Hard) {
                c.state = State::Learning;
                c.due = in_minutes(p_.hard_step_min);
            } else if (rating == Rating::Good && c.step == 0) {
                c.state = State::Learning;
                c.step = 1;
                c.due = in_minutes(p_.good_step_min);
            } else {
                graduate();
            }
            break;
        case State::Review:
            if (rating == Rating::Again) {
                c.lapses += 1;
                c.state = State::Relearning;
                c.due = in_minutes(p_.relearn_step_min);
            } else {
                graduate();
            }
            break;
        case State::Relearning:
            if (rating == Rating::Again) {
                c.due = in_minutes(p_.relearn_step_min);
            } else {
                graduate();
            }
            break;
    }

    c.reps += 1;
    c.last_review = now;
    return c;
}

}  // namespace vocab
