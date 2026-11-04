#include "vocab_engine/comfort.hpp"

#include <algorithm>
#include <cmath>

namespace vocab {

namespace {
constexpr double kMinMs = 300.0;
constexpr double kMaxMs = 120000.0;

double log_ms(double ms) { return std::log(std::clamp(ms, kMinMs, kMaxMs)); }

Rating cap(Rating r, Rating max) {
    return static_cast<int>(r) > static_cast<int>(max) ? max : r;
}
}  // namespace

int mode_level(Mode mode) {
    switch (mode) {
        case Mode::Flashcard:
        case Mode::Meaning:
            return 1;
        case Mode::Cloze:
            return 2;
        case Mode::Synonyms:
            return 3;
        case Mode::Usage:
            return 4;
    }
    return 1;
}

double ComfortModel::speed_z(const Evidence& ev, const SpeedBaselines& b) const {
    const SpeedStats& s = b.by_mode[static_cast<int>(ev.mode)];
    if (s.n < p_.min_samples_for_speed || ev.response_ms <= 0.0) return 0.0;
    double var = s.m2 / (s.n - 1.0);
    double sd = std::sqrt(std::max(var, 1e-6));
    return (log_ms(ev.response_ms) - s.mean) / sd;
}

Rating ComfortModel::implicit_rating(const Evidence& ev, const SpeedBaselines& b) const {
    if (!ev.correct) return Rating::Again;

    // Flashcards are self-rated; only a declared guess can pull the rating down.
    if (ev.mode == Mode::Flashcard && ev.self_rating >= 1 && ev.self_rating <= 4) {
        Rating r = static_cast<Rating>(ev.self_rating);
        return ev.confidence == Confidence::Guess ? cap(r, Rating::Hard) : r;
    }

    if (ev.hint_used || ev.confidence == Confidence::Guess) return Rating::Hard;

    double z = speed_z(ev, b);
    if (z > p_.slow_z) return Rating::Hard;

    bool fast = z < p_.fast_z;
    bool sure = ev.confidence == Confidence::Sure;
    // Harder modes are stronger evidence: a quick, confident answer at the
    // discriminate/use levels earns Easy.
    if (fast && sure) return Rating::Easy;
    if (mode_level(ev.mode) >= 3 && sure && z < 0.0) return Rating::Easy;
    return Rating::Good;
}

void ComfortModel::update_speed(SpeedBaselines& b, const Evidence& ev) {
    if (ev.response_ms <= 0.0) return;
    SpeedStats& s = b.by_mode[static_cast<int>(ev.mode)];
    double x = log_ms(ev.response_ms);
    s.n += 1.0;
    double delta = x - s.mean;
    s.mean += delta / s.n;
    s.m2 += delta * (x - s.mean);
}

void ComfortModel::update_depth(WordCard& c, const Evidence& ev, Rating rating,
                                double now, bool& promoted, bool& demoted) const {
    int level = mode_level(ev.mode);
    int frontier = std::min(c.depth + 1, kMaxDepth);

    if (rating == Rating::Again) {
        if (level <= c.depth) {
            // Failed a level already "mastered": drop below it.
            c.depth = std::max(0, std::min(c.depth - 1, level - 1));
            demoted = true;
        }
        c.streak = 0;
        return;
    }

    if (level != frontier || c.depth >= kMaxDepth) return;
    // A self-rated "Hard" flashcard is not evidence of mastery.
    if (rating == Rating::Hard && ev.mode == Mode::Flashcard) return;

    bool spaced = c.streak == 0 || (now - c.last_streak_at) >= p_.streak_spacing_days;
    if (!spaced) return;

    c.streak += 1;
    c.last_streak_at = now;
    if (c.streak >= p_.promote_after) {
        c.depth = std::min(c.depth + 1, kMaxDepth);
        c.streak = 0;
        promoted = true;
    }
}

void ComfortModel::update_calibration(WordCard& c, const Evidence& ev) const {
    double target;
    switch (ev.confidence) {
        case Confidence::Sure:
            target = ev.correct ? 1.0 : 0.0;
            break;
        case Confidence::Unsure:
            target = ev.correct ? 0.7 : 0.3;
            break;
        case Confidence::Guess:
            target = ev.correct ? 0.4 : 0.3;
            break;
        case Confidence::None:
        default:
            return;
    }
    c.calibration += p_.calibration_alpha * (target - c.calibration);
}

double ComfortModel::comfort(const WordCard& c, double now) const {
    if (c.state == State::New && c.reps == 0) return 0.0;
    double r = fsrs_.retrievability_at(c, now);
    double depth = static_cast<double>(c.depth) / kMaxDepth;
    double stab = std::min(1.0, std::log1p(c.stability) / std::log1p(p_.stability_target_days));
    double score = p_.w_retrievability * r + p_.w_depth * depth +
                   p_.w_stability * stab + p_.w_calibration * c.calibration;
    score = std::clamp(100.0 * score, 0.0, 100.0);
    // Right after a review R is ~1 even for a word seen once; words still in
    // learning steps stay in the Learning tier until they graduate.
    if (c.state == State::Learning || c.state == State::Relearning) {
        score = std::min(score, 39.0);
    }
    return score;
}

Tier ComfortModel::tier(const WordCard& c, double now) const {
    if (c.state == State::New && c.reps == 0) return Tier::New;
    double s = comfort(c, now);
    if (s >= 85.0) return Tier::Mastered;
    if (s >= 65.0) return Tier::Comfortable;
    if (s >= 40.0) return Tier::Shaky;
    return Tier::Learning;
}

double ComfortModel::priority(const WordCard& c, double now) const {
    double r = fsrs_.retrievability_at(c, now);
    double p = (1.0 - r) + 0.3 * (1.0 - c.calibration);
    if (c.state == State::Learning || c.state == State::Relearning) p += 0.5;
    double overdue_days = std::max(0.0, now - c.due);
    p += std::min(0.5, overdue_days / 30.0);
    return p;
}

Mode ComfortModel::choose_mode(const WordCard& c, double u, bool allow_usage) const {
    // Brand-new or still in learning steps: introduce/reinforce with recognition.
    if (c.reps == 0) return Mode::Flashcard;
    if (c.state == State::Learning || c.state == State::Relearning) {
        return u < 0.5 ? Mode::Flashcard : Mode::Meaning;
    }

    int max_level = allow_usage ? kMaxDepth : kMaxDepth - 1;
    int frontier = std::min(c.depth + 1, max_level);
    int level = frontier;
    if (c.depth >= max_level) {
        // Fully mastered: keep it fresh with an even mix of every level.
        level = std::clamp(1 + static_cast<int>(u * max_level), 1, max_level);
    } else if (u >= p_.frontier_share && frontier > 1) {
        // Maintenance: spread the remaining probability over lower levels.
        double v = (u - p_.frontier_share) / (1.0 - p_.frontier_share);
        level = 1 + static_cast<int>(v * (frontier - 1));
        level = std::clamp(level, 1, frontier - 1);
    }

    switch (level) {
        case 1:
            return Mode::Meaning;
        case 2:
            return Mode::Cloze;
        case 3:
            return Mode::Synonyms;
        default:
            return Mode::Usage;
    }
}

ReviewOutcome ComfortModel::process(const WordCard& card, const Evidence& ev,
                                    const SpeedBaselines& baselines, double now) const {
    ReviewOutcome out;
    out.comfort_before = comfort(card, now);
    out.rating = implicit_rating(ev, baselines);

    WordCard c = fsrs_.review(card, out.rating, now);
    update_depth(c, ev, out.rating, now, out.promoted, out.demoted);
    update_calibration(c, ev);

    out.baselines = baselines;
    update_speed(out.baselines, ev);

    out.card = c;
    out.comfort_after = comfort(c, now);
    return out;
}

}  // namespace vocab
