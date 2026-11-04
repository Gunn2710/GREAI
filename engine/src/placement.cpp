#include "vocab_engine/placement.hpp"

#include <algorithm>
#include <cmath>

namespace vocab {

namespace {
constexpr double kGridMin = -4.0;
constexpr double kGridMax = 4.0;
constexpr int kGridPoints = 161;
}  // namespace

double p_know(double theta, double b) { return 1.0 / (1.0 + std::exp(-(theta - b))); }

double p_correct(double theta, double b, double guess) {
    return guess + (1.0 - guess) * p_know(theta, b);
}

AbilityEstimate estimate_ability(const std::vector<IrtResponse>& responses, double guess,
                                 double prior_mean, double prior_sd) {
    // Work in log space so long response lists don't underflow.
    std::vector<double> thetas(kGridPoints), logw(kGridPoints);
    double max_logw = -INFINITY;
    for (int i = 0; i < kGridPoints; ++i) {
        double t = kGridMin + (kGridMax - kGridMin) * i / (kGridPoints - 1);
        double z = (t - prior_mean) / prior_sd;
        double lw = -0.5 * z * z;
        for (const auto& r : responses) {
            double p = std::clamp(p_correct(t, r.difficulty, guess), 1e-9, 1.0 - 1e-9);
            lw += r.correct ? std::log(p) : std::log(1.0 - p);
        }
        thetas[i] = t;
        logw[i] = lw;
        max_logw = std::max(max_logw, lw);
    }

    double sum = 0.0, mean = 0.0;
    std::vector<double> w(kGridPoints);
    for (int i = 0; i < kGridPoints; ++i) {
        w[i] = std::exp(logw[i] - max_logw);
        sum += w[i];
        mean += w[i] * thetas[i];
    }
    mean /= sum;
    double var = 0.0;
    for (int i = 0; i < kGridPoints; ++i) var += w[i] * (thetas[i] - mean) * (thetas[i] - mean);
    return {mean, std::sqrt(var / sum)};
}

double update_difficulty(double b, double theta, bool correct, double guess, double k) {
    double expected = p_correct(theta, b, guess);
    return b + k * (expected - (correct ? 1.0 : 0.0));
}

double update_ability(double theta, double b, bool correct, double guess, double k) {
    double expected = p_correct(theta, b, guess);
    return theta + k * ((correct ? 1.0 : 0.0) - expected);
}

}  // namespace vocab
