// Python bindings for the vocab engine (module: vocab_engine).
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "vocab_engine/comfort.hpp"
#include "vocab_engine/fsrs.hpp"
#include "vocab_engine/placement.hpp"
#include "vocab_engine/types.hpp"

namespace py = pybind11;
using namespace vocab;

PYBIND11_MODULE(vocab_engine, m) {
    m.doc() = "FSRS scheduling and word-comfort model for GRE vocabulary";

    py::enum_<Rating>(m, "Rating")
        .value("Again", Rating::Again)
        .value("Hard", Rating::Hard)
        .value("Good", Rating::Good)
        .value("Easy", Rating::Easy);

    py::enum_<State>(m, "State")
        .value("New", State::New)
        .value("Learning", State::Learning)
        .value("Review", State::Review)
        .value("Relearning", State::Relearning);

    py::enum_<Mode>(m, "Mode")
        .value("Flashcard", Mode::Flashcard)
        .value("Meaning", Mode::Meaning)
        .value("Cloze", Mode::Cloze)
        .value("Synonyms", Mode::Synonyms)
        .value("Usage", Mode::Usage);

    py::enum_<Confidence>(m, "Confidence")
        .value("None_", Confidence::None)
        .value("Guess", Confidence::Guess)
        .value("Unsure", Confidence::Unsure)
        .value("Sure", Confidence::Sure);

    py::enum_<Tier>(m, "Tier")
        .value("New", Tier::New)
        .value("Learning", Tier::Learning)
        .value("Shaky", Tier::Shaky)
        .value("Comfortable", Tier::Comfortable)
        .value("Mastered", Tier::Mastered);

    py::class_<WordCard>(m, "WordCard")
        .def(py::init<>())
        .def_readwrite("state", &WordCard::state)
        .def_readwrite("step", &WordCard::step)
        .def_readwrite("stability", &WordCard::stability)
        .def_readwrite("difficulty", &WordCard::difficulty)
        .def_readwrite("due", &WordCard::due)
        .def_readwrite("last_review", &WordCard::last_review)
        .def_readwrite("reps", &WordCard::reps)
        .def_readwrite("lapses", &WordCard::lapses)
        .def_readwrite("depth", &WordCard::depth)
        .def_readwrite("streak", &WordCard::streak)
        .def_readwrite("last_streak_at", &WordCard::last_streak_at)
        .def_readwrite("calibration", &WordCard::calibration);

    py::class_<Evidence>(m, "Evidence")
        .def(py::init<>())
        .def_readwrite("mode", &Evidence::mode)
        .def_readwrite("correct", &Evidence::correct)
        .def_readwrite("response_ms", &Evidence::response_ms)
        .def_readwrite("hint_used", &Evidence::hint_used)
        .def_readwrite("confidence", &Evidence::confidence)
        .def_readwrite("self_rating", &Evidence::self_rating);

    py::class_<SpeedStats>(m, "SpeedStats")
        .def(py::init<>())
        .def_readwrite("n", &SpeedStats::n)
        .def_readwrite("mean", &SpeedStats::mean)
        .def_readwrite("m2", &SpeedStats::m2);

    py::class_<SpeedBaselines>(m, "SpeedBaselines")
        .def(py::init<>())
        .def("get", [](const SpeedBaselines& b, Mode mode) {
            return b.by_mode[static_cast<int>(mode)];
        })
        .def("set", [](SpeedBaselines& b, Mode mode, const SpeedStats& s) {
            b.by_mode[static_cast<int>(mode)] = s;
        });

    py::class_<FsrsParams>(m, "FsrsParams")
        .def(py::init<>())
        .def_readwrite("w", &FsrsParams::w)
        .def_readwrite("desired_retention", &FsrsParams::desired_retention)
        .def_readwrite("max_interval_days", &FsrsParams::max_interval_days);

    py::class_<ComfortParams>(m, "ComfortParams")
        .def(py::init<>())
        .def_readwrite("w_retrievability", &ComfortParams::w_retrievability)
        .def_readwrite("w_depth", &ComfortParams::w_depth)
        .def_readwrite("w_stability", &ComfortParams::w_stability)
        .def_readwrite("w_calibration", &ComfortParams::w_calibration)
        .def_readwrite("promote_after", &ComfortParams::promote_after)
        .def_readwrite("streak_spacing_days", &ComfortParams::streak_spacing_days)
        .def_readwrite("frontier_share", &ComfortParams::frontier_share);

    py::class_<ReviewOutcome>(m, "ReviewOutcome")
        .def_readonly("card", &ReviewOutcome::card)
        .def_readonly("baselines", &ReviewOutcome::baselines)
        .def_readonly("rating", &ReviewOutcome::rating)
        .def_readonly("promoted", &ReviewOutcome::promoted)
        .def_readonly("demoted", &ReviewOutcome::demoted)
        .def_readonly("comfort_before", &ReviewOutcome::comfort_before)
        .def_readonly("comfort_after", &ReviewOutcome::comfort_after);

    py::class_<Fsrs>(m, "Fsrs")
        .def(py::init<FsrsParams>(), py::arg("params") = FsrsParams{})
        .def_static("retrievability", &Fsrs::retrievability)
        .def("retrievability_at", &Fsrs::retrievability_at)
        .def("review", &Fsrs::review)
        .def("next_interval", &Fsrs::next_interval);

    py::class_<ComfortModel>(m, "ComfortModel")
        .def(py::init<FsrsParams, ComfortParams>(), py::arg("fsrs") = FsrsParams{},
             py::arg("params") = ComfortParams{})
        .def("process", &ComfortModel::process)
        .def("implicit_rating", &ComfortModel::implicit_rating)
        .def("speed_z", &ComfortModel::speed_z)
        .def("comfort", &ComfortModel::comfort)
        .def("tier", &ComfortModel::tier)
        .def("priority", &ComfortModel::priority)
        .def("choose_mode", &ComfortModel::choose_mode)
        .def("retrievability_at", [](const ComfortModel& m, const WordCard& c, double now) {
            return m.fsrs().retrievability_at(c, now);
        });

    m.def("mode_level", &mode_level);

    py::class_<IrtResponse>(m, "IrtResponse")
        .def(py::init<>())
        .def(py::init([](double difficulty, bool correct) { return IrtResponse{difficulty, correct}; }),
             py::arg("difficulty"), py::arg("correct"))
        .def_readwrite("difficulty", &IrtResponse::difficulty)
        .def_readwrite("correct", &IrtResponse::correct);

    py::class_<AbilityEstimate>(m, "AbilityEstimate")
        .def_readonly("theta", &AbilityEstimate::theta)
        .def_readonly("se", &AbilityEstimate::se);

    m.def("p_know", &p_know, py::arg("theta"), py::arg("b"));
    m.def("p_correct", &p_correct, py::arg("theta"), py::arg("b"), py::arg("guess") = 0.2);
    m.def("estimate_ability", &estimate_ability, py::arg("responses"), py::arg("guess") = 0.2,
          py::arg("prior_mean") = 0.0, py::arg("prior_sd") = 1.0);
    m.def("update_difficulty", &update_difficulty, py::arg("b"), py::arg("theta"), py::arg("correct"),
          py::arg("guess") = 0.2, py::arg("k") = 0.05);
    m.def("update_ability", &update_ability, py::arg("theta"), py::arg("b"), py::arg("correct"),
          py::arg("guess") = 0.2, py::arg("k") = 0.3);
}
