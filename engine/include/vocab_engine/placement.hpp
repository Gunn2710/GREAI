// Placement test: estimate a user's vocabulary level (theta) from a short set
// of answers, using a one-parameter IRT model with a guessing floor.
//
// theta and word difficulty b share one scale: a user with theta == b knows
// the word with probability 0.5.
#pragma once

#include <vector>

namespace vocab {

struct IrtResponse {
    double difficulty = 0.0;  // b
    bool correct = false;
};

struct AbilityEstimate {
    double theta = 0.0;
    double se = 1.0;  // posterior standard deviation
};

// Probability the user actually knows a word (no guessing).
double p_know(double theta, double b);

// Probability of answering a multiple-choice item correctly: knows it, or
// doesn't and guesses right with probability `guess`.
double p_correct(double theta, double b, double guess);

// Expected a posteriori estimate on a grid, with a Normal(prior_mean, prior_sd) prior.
AbilityEstimate estimate_ability(const std::vector<IrtResponse>& responses, double guess = 0.2,
                                 double prior_mean = 0.0, double prior_sd = 1.0);

// Elo-style nudge to a word's difficulty after one answer from a user of
// ability theta: harder if they missed it, easier if they got it.
double update_difficulty(double b, double theta, bool correct, double guess = 0.2,
                         double k = 0.05);

// The matching nudge to a user's ability after answering an item of difficulty b.
double update_ability(double theta, double b, bool correct, double guess = 0.2, double k = 0.3);

}  // namespace vocab
