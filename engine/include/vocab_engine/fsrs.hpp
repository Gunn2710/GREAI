// FSRS-5 memory model: stability, difficulty and retrievability per card,
// plus learning steps and interval scheduling.
#pragma once

#include <array>

#include "vocab_engine/types.hpp"

namespace vocab {

struct FsrsParams {
    // FSRS-5 default weights. Replace with per-user optimized weights once a
    // user has enough review history.
    std::array<double, 19> w{0.40255, 1.18385, 3.173,  15.69105, 7.1949,
                             0.5345,  1.4604,  0.0046, 1.54575,  0.1192,
                             1.01925, 1.9395,  0.11,   0.29605,  2.2698,
                             0.2315,  2.9898,  0.51655, 0.6621};
    double desired_retention = 0.9;
    double max_interval_days = 365.0;
    // Learning steps in minutes (New/Learning) and relearning step (Relearning).
    double again_step_min = 1.0;
    double hard_step_min = 6.0;
    double good_step_min = 10.0;
    double relearn_step_min = 10.0;
};

class Fsrs {
public:
    explicit Fsrs(FsrsParams params = {}) : p_(params) {}

    // Probability of recall `elapsed_days` after the last review.
    static double retrievability(double elapsed_days, double stability);

    // Retrievability of a card at time `now` (1.0 for unseen cards).
    double retrievability_at(const WordCard& card, double now) const;

    // Apply a rating at time `now`; updates memory state, state machine and due.
    WordCard review(WordCard card, Rating rating, double now) const;

    // Interval in days that hits the desired retention for a given stability.
    double next_interval(double stability) const;

    const FsrsParams& params() const { return p_; }

private:
    double init_stability(Rating g) const;
    double init_difficulty(Rating g) const;
    double next_difficulty(double d, Rating g) const;
    double recall_stability(double d, double s, double r, Rating g) const;
    double forget_stability(double d, double s, double r) const;
    double short_term_stability(double s, Rating g) const;

    FsrsParams p_;
};

}  // namespace vocab
