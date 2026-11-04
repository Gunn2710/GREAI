// Comfort model: turns raw interactions into FSRS ratings, moves words along
// the depth ladder, tracks confidence calibration and personal speed, and
// combines everything into a 0-100 comfort score.
#pragma once

#include "vocab_engine/fsrs.hpp"
#include "vocab_engine/types.hpp"

namespace vocab {

enum class Tier : int { New = 0, Learning = 1, Shaky = 2, Comfortable = 3, Mastered = 4 };

struct ComfortParams {
    // Comfort score weights (sum to 1).
    double w_retrievability = 0.45;
    double w_depth = 0.30;
    double w_stability = 0.15;
    double w_calibration = 0.10;
    double stability_target_days = 60.0;

    // Depth ladder.
    int promote_after = 2;              // spaced successes needed to climb a level
    double streak_spacing_days = 0.25;  // successes closer than this count once

    // Implicit grading from response time (z-score of log ms vs. personal baseline).
    double slow_z = 1.0;
    double fast_z = -0.5;
    double min_samples_for_speed = 5.0;

    double calibration_alpha = 0.3;

    // Mode selection: share of items at the frontier level (rest is maintenance).
    double frontier_share = 0.7;
};

struct ReviewOutcome {
    WordCard card;
    SpeedBaselines baselines;
    Rating rating = Rating::Good;
    bool promoted = false;
    bool demoted = false;
    double comfort_before = 0.0;
    double comfort_after = 0.0;
};

int mode_level(Mode mode);

class ComfortModel {
public:
    explicit ComfortModel(FsrsParams fsrs = {}, ComfortParams params = {})
        : fsrs_(fsrs), p_(params) {}

    // Full update for one interaction: grade, schedule, ladder, calibration, speed.
    ReviewOutcome process(const WordCard& card, const Evidence& ev,
                          const SpeedBaselines& baselines, double now) const;

    // Map evidence to an FSRS rating without the user rating themselves.
    Rating implicit_rating(const Evidence& ev, const SpeedBaselines& baselines) const;

    // Response-time z-score against the user's own baseline for this mode (0 if
    // there is not enough data yet).
    double speed_z(const Evidence& ev, const SpeedBaselines& baselines) const;

    double comfort(const WordCard& card, double now) const;
    Tier tier(const WordCard& card, double now) const;

    // Higher means "show this sooner" among cards that are already due.
    double priority(const WordCard& card, double now) const;

    // Pick a quiz mode for a card. `u` is a uniform random number in [0, 1).
    Mode choose_mode(const WordCard& card, double u, bool allow_usage) const;

    const Fsrs& fsrs() const { return fsrs_; }
    const ComfortParams& params() const { return p_; }

private:
    void update_depth(WordCard& card, const Evidence& ev, Rating rating, double now,
                      bool& promoted, bool& demoted) const;
    void update_calibration(WordCard& card, const Evidence& ev) const;
    static void update_speed(SpeedBaselines& b, const Evidence& ev);

    Fsrs fsrs_;
    ComfortParams p_;
};

}  // namespace vocab
