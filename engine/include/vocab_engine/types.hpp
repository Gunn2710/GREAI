// Core types shared by the scheduler (FSRS) and the comfort model.
// All timestamps are expressed in fractional days since the Unix epoch.
#pragma once

#include <array>
#include <cstdint>

namespace vocab {

enum class Rating : int { Again = 1, Hard = 2, Good = 3, Easy = 4 };

enum class State : int { New = 0, Learning = 1, Review = 2, Relearning = 3 };

// Quiz modes. Each mode probes one level of the depth ladder.
enum class Mode : int {
    Flashcard = 0,  // level 1: recognize (self-rated)
    Meaning = 1,    // level 1: recognize (pick the definition)
    Cloze = 2,      // level 2: recall the word from context
    Synonyms = 3,   // level 3: discriminate (pick the synonym pair)
    Usage = 4,      // level 4: produce a sentence (AI graded)
};

enum class Confidence : int { None = 0, Guess = 1, Unsure = 2, Sure = 3 };

constexpr int kMaxDepth = 4;

// Per-user, per-word state. Mirrors the `cards` table one-to-one.
struct WordCard {
    // Memory model (FSRS)
    State state = State::New;
    int step = 0;              // learning-step index while Learning
    double stability = 0.0;    // days until recall probability drops to 90%
    double difficulty = 0.0;   // 1 (easy) .. 10 (hard)
    double due = 0.0;
    double last_review = 0.0;
    int reps = 0;
    int lapses = 0;

    // Comfort model
    int depth = 0;                // highest depth-ladder level mastered (0..4)
    int streak = 0;               // consecutive spaced successes at the frontier level
    double last_streak_at = 0.0;  // when the streak last advanced
    double calibration = 0.5;     // EMA of "confidence matched the outcome"
};

// One observed interaction with a word.
struct Evidence {
    Mode mode = Mode::Meaning;
    bool correct = false;
    double response_ms = 0.0;
    bool hint_used = false;
    Confidence confidence = Confidence::None;
    int self_rating = 0;  // 1..4 for Flashcard mode, 0 otherwise
};

// Online mean/variance (Welford) of log response time for one mode.
struct SpeedStats {
    double n = 0.0;
    double mean = 0.0;
    double m2 = 0.0;
};

// A user's personal response-time baselines, one per mode.
struct SpeedBaselines {
    std::array<SpeedStats, 5> by_mode{};
};

}  // namespace vocab
