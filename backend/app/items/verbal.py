"""GRE Verbal item types served from the stored question bank (`items` table).

    tc  Text Completion: 1-3 blanks; 5 options for one blank, 3 per blank
        otherwise; credit only if every blank is right.
    se  Sentence Equivalence: one blank, 6 options, pick the two that each
        complete the sentence with the same meaning.
    rc  Reading Comprehension: a passage and one question about it; either
        pick one of 5 options or select every right one of 3.
"""
import random
import re

from sqlalchemy import select

from app.items.base import BuiltItem, Grade, ItemType, register
from app.models import IssuedItem, Item, Word

MARKER = re.compile(r"\{(\d)\}")


def fill(text: str, answers: list[str]) -> str:
    """The passage with each blank replaced by its correct answer."""
    return MARKER.sub(lambda m: answers[int(m.group(1)) - 1], text)


def bank_words(db, labels: list[str]) -> list[dict]:
    """Options that are vocabulary-bank words, for linking to word pages."""
    rows = db.scalars(select(Word).where(Word.lemma.in_(labels)))
    return [{"id": w.id, "lemma": w.lemma, "definition": w.definition} for w in rows]


def _reveal(db, item: IssuedItem, answers: list[str]) -> dict:
    all_labels = [o for opts in item.payload.get("blanks", [item.payload.get("options", [])]) for o in opts]
    return {
        "explanation": item.answer["explanation"],
        "filled_text": fill(item.payload["text"], answers),
        "words": bank_words(db, all_labels),
    }


class TextCompletion(ItemType):
    name, section, hint_available = "tc", "verbal", True

    def build(self, db, user_id, item: Item) -> BuiltItem:
        rng = random.Random()
        blanks, indices = [], []
        for opts in item.content["blanks"]:
            shuffled = opts[:]
            rng.shuffle(shuffled)
            blanks.append(shuffled)
            indices.append(shuffled.index(opts[0]))  # authored: first option is correct
        return BuiltItem(
            payload={"text": item.content["text"], "blanks": blanks, "difficulty": item.difficulty_label},
            answer={
                "indices": indices,
                "clue": item.content["clue"],
                "explanation": item.content["explanation"],
            },
        )

    async def grade(self, db, item, response) -> Grade:
        selected = response.get("selected")
        answer = item.answer["indices"]
        ok = isinstance(selected, list) and selected == answer
        answers = [item.payload["blanks"][b][i] for b, i in enumerate(answer)]
        return Grade(
            correct=ok, score=1.0 if ok else 0.0,
            feedback={"correct_indices": answer, **_reveal(db, item, answers)},
        )

    def hint(self, item):
        return {"clue": item.answer["clue"]}


class SentenceEquivalence(ItemType):
    name, section, hint_available = "se", "verbal", True

    def build(self, db, user_id, item: Item) -> BuiltItem:
        options = item.content["options"][:]
        correct = set(options[:2])  # authored: first two options are the correct pair
        random.Random().shuffle(options)
        return BuiltItem(
            payload={"text": item.content["text"], "options": options, "difficulty": item.difficulty_label},
            answer={
                "indices": sorted(i for i, o in enumerate(options) if o in correct),
                "clue": item.content["clue"],
                "explanation": item.content["explanation"],
            },
        )

    async def grade(self, db, item, response) -> Grade:
        selected = response.get("selected") or []
        answer = item.answer["indices"]
        ok = isinstance(selected, list) and sorted(selected) == answer
        first = item.payload["options"][answer[0]]
        return Grade(
            correct=ok, score=1.0 if ok else 0.0,
            feedback={"correct_indices": answer, **_reveal(db, item, [first])},
        )

    def hint(self, item):
        return {"clue": item.answer["clue"]}


def passage_words(db, passage: str) -> list[dict]:
    """Bank words that appear in a passage as written."""
    return bank_words(db, sorted(set(re.findall(r"[a-z]+", passage.lower()))))


class ReadingComprehension(ItemType):
    name, section, hint_available = "rc", "verbal", True

    def build(self, db, user_id, item: Item) -> BuiltItem:
        c = item.content
        options = c["options"][:]
        correct = set(options[: 1 if c["select"] == "one" else c["correct"]])  # authored first
        random.Random().shuffle(options)
        return BuiltItem(
            payload={
                "passage": c["passage"], "topic": c["topic"], "order": c["order"], "of": c["of"],
                "question": c["question"], "options": options, "select": c["select"],
                "difficulty": item.difficulty_label,
            },
            answer={
                "indices": sorted(i for i, o in enumerate(options) if o in correct),
                "clue": c["clue"],
                "explanation": c["explanation"],
            },
        )

    async def grade(self, db, item, response) -> Grade:
        selected = response.get("selected")
        answer = item.answer["indices"]
        ok = isinstance(selected, list) and sorted(selected) == answer
        return Grade(
            correct=ok, score=1.0 if ok else 0.0,
            feedback={
                "correct_indices": answer,
                "explanation": item.answer["explanation"],
                "words": passage_words(db, item.payload["passage"]),
            },
        )

    def hint(self, item):
        return {"clue": item.answer["clue"]}


register(TextCompletion())
register(SentenceEquivalence())
register(ReadingComprehension())
