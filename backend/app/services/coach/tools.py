"""What the coach can see and do: the progress snapshot, the tools it can call
to look further, the actions it can offer (each confirmed by the student with
a button), and its notes about the student."""
import json
from collections import Counter
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from app import engine_bridge as eb
from app.models import Attempt, Card, CoachNote, Confusion, Word, utcnow
from app.services import placement, practice, stats
from app.services.ai import word_entry
from app.services.sets import word_sets
from app.services.study import MAX_SENTENCE, get_profile, my_sentence, new_word_limit

# Practice question types the coach can open: (section, kind on the Practice page, label).
PRACTICE_KINDS = {
    "tc": ("verbal", "tc", "Text Completion"),
    "se": ("verbal", "se", "Sentence Equivalence"),
    "rc": ("verbal", "rc", "Reading Comprehension"),
    "verbal": ("verbal", "mixed", "Verbal (mixed)"),
    "qc": ("quant", "qc", "Quantitative Comparison"),
    "qmc": ("quant", "qmc", "Quant multiple choice"),
    "qne": ("quant", "qne", "Quant numeric entry"),
    "quant": ("quant", "quant", "Quant (mixed)"),
}
FREQUENCY = {"less": "review", "balanced": "balanced", "more": "new"}
STUDY_MODE = {"mixed": "mixed", "flashcards": "flashcard", "multiple_choice": "mcq"}
MAX_ACTIONS = 4
MAX_NOTES = 30
MAX_NOTE = 200


PLAN_FIELDS = ("test_date", "target_verbal", "target_quant", "daily_new_words")


def plan_of(profile) -> dict:
    return {
        "test_date": profile.test_date.isoformat() if profile.test_date else None,
        "target_verbal": profile.target_verbal,
        "target_quant": profile.target_quant,
        "daily_new_words": profile.daily_new_words,
    }


def snapshot(db: Session, user_id: str) -> dict:
    """What the coach knows up front: the plan, vocab, practice and placement."""
    today = utcnow().date()
    profile = get_profile(db, user_id)
    dash = stats.dashboard(db, user_id)
    started = sum(v for k, v in dash["tiers"].items() if k != "new")
    days_left = (profile.test_date - today).days if profile.test_date else None
    words_left = dash["total_words"] - started
    level = placement.latest(db, user_id)
    current = dash["sets"]["current"]
    return {
        "today": today.isoformat(),
        "plan": {
            **plan_of(profile),
            "days_until_test": days_left,
            "new_word_limit_today": new_word_limit(profile),
        },
        "vocab": {
            "words_in_bank": dash["total_words"],
            "words_started": started,
            "words_not_started": words_left,
            "by_comfort": dash["tiers"],
            "sets_done": dash["sets"]["done"],
            "sets_total": dash["sets"]["total"],
            "current_set": {k: current[k] for k in ("number", "size", "started", "learned")} if current else None,
            "reviews_due_now": dash["due_now"],
            "new_words_left_today": dash["new_available_today"],
            "answered_today": dash["reviews_today"],
            "accuracy_last_30_days": dash["accuracy_30d"],
            "streak_days": dash["streak_days"],
            "new_words_per_day_to_finish_by_test": (
                round(words_left / days_left, 1) if days_left and days_left > 0 else None
            ),
        },
        "placement": {"level": level["level"], "theta": level["theta"]} if level else None,
        "practice": [
            {"type": v["name"], "section": v["section"], "rating": v["rating"], "attempts": v["attempts"],
             "accuracy": v["accuracy"], "questions_available": v["questions"]}
            for v in practice.summary(db, user_id).values()
        ],
    }


class Tools:
    def __init__(self, db: Session, user_id: str):
        self.db, self.user_id = db, user_id
        self.proposal: dict | None = None
        self.actions: list[dict] = []  # offered actions and note changes, in order

    def __call__(self, name: str, args: dict) -> str:
        match name:
            case "vocab_sets":
                return self.vocab_sets()
            case "weak_spots":
                return self.weak_spots()
            case "recent_activity":
                return self.recent_activity()
            case "look_up_word":
                return self.look_up_word(str(args.get("word", "")))
            case "find_words_by_meaning":
                return self.find_words_by_meaning(str(args.get("phrase", "")))
            case "word_history":
                return self.word_history(str(args.get("word", "")))
            case "propose_plan":
                return self.propose_plan(args)
            case "review_now":
                return self.review_now(args.get("words"), str(args.get("title", "")))
            case "mark_known":
                return self.mark_known(str(args.get("word", "")))
            case "propose_study_settings":
                return self.propose_study_settings(args)
            case "open_practice":
                return self.open_practice(str(args.get("kind", "")))
            case "save_sentence":
                return self.save_sentence(str(args.get("word", "")), str(args.get("sentence", "")))
            case "remember":
                return self.remember(str(args.get("note", "")))
            case "forget":
                return self.forget(args.get("note_id"))
        raise ValueError(f"unknown tool {name}")

    def _word(self, lemma: str) -> Word | None:
        return self.db.scalar(select(Word).where(func.lower(Word.lemma) == lemma.strip().lower()))

    def vocab_sets(self) -> str:
        data = word_sets(self.db, self.user_id)
        keep = ("number", "size", "started", "learned", "status")
        return json.dumps({"current_set": data["current"],
                           "sets": [{k: s[k] for k in keep} for s in data["sets"]]})

    def weak_spots(self) -> str:
        now = eb.now_days()
        cards = self.db.scalars(select(Card).where(Card.user_id == self.user_id, Card.reps > 0)).all()
        weakest = sorted(((c, eb.card_summary(c, now)) for c in cards), key=lambda x: x[1]["comfort"])[:10]
        names = {w.id: w.lemma for w in self.db.scalars(
            select(Word).where(Word.id.in_([c.word_id for c, _ in weakest])))}
        target, chosen = Word.__table__.alias("t"), Word.__table__.alias("c")
        confused = self.db.execute(
            select(target.c.lemma, chosen.c.lemma, Confusion.count)
            .join(target, target.c.id == Confusion.target_word_id)
            .join(chosen, chosen.c.id == Confusion.chosen_word_id)
            .where(Confusion.user_id == self.user_id)
            .order_by(Confusion.count.desc()).limit(8)
        ).all()
        return json.dumps({
            "weakest_words": [{"word": names.get(c.word_id), "tier": s["tier"], "comfort": round(s["comfort"], 2),
                               "lapses": s["lapses"]} for c, s in weakest],
            "confused_pairs": [{"answer_was": a, "picked": b, "times": n} for a, b, n in confused],
        })

    def recent_activity(self) -> str:
        since = utcnow() - timedelta(days=14)
        rows = self.db.execute(
            select(Attempt.created_at, Attempt.section, Attempt.item_type, Attempt.correct)
            .where(Attempt.user_id == self.user_id, Attempt.created_at >= since)
        ).all()
        days: dict[str, Counter] = {}
        for created, section, item_type, correct in rows:
            day = eb.from_days(eb.to_days(created)).date().isoformat()
            kind = "vocab" if item_type in stats.VOCAB_TYPES else f"{section}_practice"
            c = days.setdefault(day, Counter())
            c[kind] += 1
            c["correct"] += bool(correct)
        return json.dumps({
            "days": [{"date": d, **dict(c)} for d, c in sorted(days.items())],
            "note": "Days with no activity are left out.",
        })

    def look_up_word(self, lemma: str) -> str:
        w = self._word(lemma)
        return word_entry(w) if w else f"“{lemma}” is not in the word bank."

    def find_words_by_meaning(self, phrase: str) -> str:
        phrase = phrase.strip()[:60]
        if not phrase:
            return "Give a phrase to search for."
        like = f"%{phrase}%"
        rows = self.db.scalars(
            select(Word).where(or_(Word.definition.ilike(like), cast(Word.synonyms, Text).ilike(like)))
            .order_by(Word.set_rank.asc().nulls_last()).limit(8)
        ).all()
        if not rows:
            return f"No words in the bank match “{phrase}”."
        return "\n".join(f"{w.lemma} ({w.pos}): {w.definition}" for w in rows)

    def word_history(self, lemma: str) -> str:
        word = self._word(lemma)
        if word is None:
            return f"“{lemma}” is not in the word bank."
        card = self.db.get(Card, (self.user_id, word.id))
        attempts = self.db.scalars(
            select(Attempt).where(Attempt.user_id == self.user_id, Attempt.word_id == word.id)
            .order_by(Attempt.created_at.desc()).limit(10)
        ).all()
        confused = self.db.execute(
            select(Word.lemma, Confusion.count).join(Word, Word.id == Confusion.chosen_word_id)
            .where(Confusion.user_id == self.user_id, Confusion.target_word_id == word.id)
            .order_by(Confusion.count.desc()).limit(5)
        ).all()
        return json.dumps({
            "word": word.lemma,
            "card": eb.card_summary(card, eb.now_days()) if card else None,
            "their_own_sentence": my_sentence(self.db, self.user_id, word.id),
            "recent_attempts": [{"type": a.item_type, "correct": a.correct, "when": a.created_at.date().isoformat()}
                                for a in attempts],
            "confused_with": [{"word": w, "times": n} for w, n in confused],
        }, default=str)

    def propose_plan(self, args: dict) -> str:
        changes, problems = {}, []
        for key in PLAN_FIELDS:
            value = args.get(key)
            if value is None:
                continue
            if key == "test_date":
                try:
                    day = date.fromisoformat(str(value))
                except ValueError:
                    problems.append("test_date must be YYYY-MM-DD")
                    continue
                if day < utcnow().date():
                    problems.append("test_date can't be in the past")
                    continue
                changes[key] = day.isoformat()
            else:
                lo, hi = (0, 100) if key == "daily_new_words" else (130, 170)
                if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
                    problems.append(f"{key} must be a whole number from {lo} to {hi}")
                    continue
                changes[key] = value
        if problems:
            return "Not shown to the student: " + "; ".join(problems)
        if not changes:
            return "Nothing to propose: include at least one field."
        self.proposal = {**(self.proposal or {}), **changes}
        return "Shown to the student with a Save button. It is not saved until they click it."

    # ---- actions: each is shown with a button, and nothing happens until it's clicked ----

    def _offer(self, action: dict) -> str:
        if sum(a["type"] not in ("noted", "forgot") for a in self.actions) >= MAX_ACTIONS:
            return f"Not shown: at most {MAX_ACTIONS} offers per reply."
        self.actions.append(action)
        return "Shown to the student with a button. Nothing happens until they click it."

    def review_now(self, words, title: str) -> str:
        if not isinstance(words, list) or not words:
            return "Not shown: give at least one word."
        found, skipped = [], []
        for lemma in [str(w) for w in words][:20]:
            word = self._word(lemma)
            if word is not None and self.db.get(Card, (self.user_id, word.id)) is not None:
                if all(f["id"] != word.id for f in found):
                    found.append({"id": word.id, "lemma": word.lemma})
            else:
                skipped.append(lemma)
        if not found:
            return "Not shown: none of those words have been started yet."
        result = self._offer({"type": "review_now", "title": title.strip()[:60] or "Review these words now",
                              "words": found})
        if skipped:
            result += f" Left out (not started or not in the word bank): {', '.join(skipped)}."
        return result

    def mark_known(self, lemma: str) -> str:
        word = self._word(lemma)
        if word is None:
            return f"Not shown: “{lemma}” is not in the word bank."
        return self._offer({"type": "mark_known", "word": {"id": word.id, "lemma": word.lemma}})

    def propose_study_settings(self, args: dict) -> str:
        changes = {}
        if args.get("new_word_frequency") is not None:
            if args["new_word_frequency"] not in FREQUENCY:
                return "Not shown: new_word_frequency must be less, balanced or more."
            changes["focus"] = FREQUENCY[args["new_word_frequency"]]
        if args.get("study_mode") is not None:
            if args["study_mode"] not in STUDY_MODE:
                return "Not shown: study_mode must be mixed, flashcards or multiple_choice."
            changes["format"] = STUDY_MODE[args["study_mode"]]
        if not changes:
            return "Nothing to propose: include at least one setting."
        return self._offer({"type": "study_settings", "changes": changes})

    def open_practice(self, kind: str) -> str:
        if kind not in PRACTICE_KINDS:
            return f"Not shown: kind must be one of {', '.join(PRACTICE_KINDS)}."
        section, page_kind, label = PRACTICE_KINDS[kind]
        return self._offer({"type": "open_practice", "section": section, "kind": page_kind, "label": label})

    def save_sentence(self, lemma: str, sentence: str) -> str:
        word = self._word(lemma)
        if word is None:
            return f"Not shown: “{lemma}” is not in the word bank."
        sentence = " ".join(sentence.split())
        if not sentence or len(sentence) > MAX_SENTENCE:
            return f"Not shown: the sentence must be 1 to {MAX_SENTENCE} characters."
        stem = word.lemma.lower()[: max(4, len(word.lemma) - 2)]
        if stem not in sentence.lower():
            return f"Not shown: the sentence doesn't use “{word.lemma}”."
        return self._offer({"type": "save_sentence", "word": {"id": word.id, "lemma": word.lemma},
                            "sentence": sentence})

    # ---- notes: saved right away; the student can see and delete them ----

    def remember(self, note: str) -> str:
        note = " ".join(note.split())[:MAX_NOTE]
        if not note:
            return "Nothing saved: the note is empty."
        if len(notes(self.db, self.user_id)) >= MAX_NOTES:
            return f"Not saved: you already have {MAX_NOTES} notes. Forget an outdated one first."
        row = CoachNote(user_id=self.user_id, text=note)
        self.db.add(row)
        self.db.commit()
        self.actions.append({"type": "noted", "text": note})
        return f"Saved as note {row.id}."

    def forget(self, note_id) -> str:
        row = self.db.get(CoachNote, note_id) if isinstance(note_id, int) else None
        if row is None or row.user_id != self.user_id:
            return "No note with that id."
        self.actions.append({"type": "forgot", "text": row.text})
        self.db.delete(row)
        self.db.commit()
        return "Deleted."


def notes(db: Session, user_id: str) -> list[dict]:
    """The coach's notes about the student, oldest first."""
    rows = db.scalars(select(CoachNote).where(CoachNote.user_id == user_id).order_by(CoachNote.id)).all()
    return [{"id": n.id, "text": n.text, "created_at": n.created_at.isoformat()} for n in rows]


def delete_note(db: Session, user_id: str, note_id: int) -> None:
    row = db.get(CoachNote, note_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    db.delete(row)
    db.commit()
