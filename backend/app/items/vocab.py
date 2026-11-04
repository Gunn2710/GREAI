"""Vocabulary item types: one per level of the depth ladder.

    flashcard / meaning  -> level 1 (recognize)
    cloze                -> level 2 (recall from context)
    synonyms             -> level 3 (discriminate near-synonyms from look-alikes)
    usage                -> level 4 (produce; graded by Claude)
"""
import random
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.items.base import BuiltItem, Grade, ItemType, register
from app.models import Confusion, IssuedItem, Word
from app.seed.seed import cluster_groups
from app.services.ai import claude

BLANK = "_____"


def _pool(db: Session) -> tuple[list[Word], dict[str, str]]:
    """All words plus the cluster -> confusion-group map."""
    return list(db.scalars(select(Word))), cluster_groups(db)


def related(a: Word, b: Word) -> bool:
    return a.lemma in b.synonyms or b.lemma in a.synonyms


def _confused_ids(db: Session, user_id: str, word_id: int) -> list[int]:
    rows = db.scalars(
        select(Confusion)
        .where(Confusion.user_id == user_id, Confusion.target_word_id == word_id)
        .order_by(Confusion.count.desc())
    )
    return [r.chosen_word_id for r in rows]


def pick_distractors(
    target: Word,
    pool: list[Word],
    n: int,
    *,
    groups: dict[str, str],
    confused_ids: list[int] = (),
    prefer_pos: bool = False,
    avoid_opposites: bool = False,
    avoid_terms: frozenset[str] = frozenset(),
    rng: random.Random,
) -> list[Word]:
    """Wrong options from other confusion groups, at most one per group.

    A group is a cluster's family (near-synonym clusters such as "soothe" and
    "ease"), so no two options can reasonably be read as meaning the same thing.
    Words the user has confused with the target come first, then the target's
    known look-alikes, then (optionally) same part of speech, then the rest.
    `avoid_opposites` drops antonym groups: in a sentence, an opposite word
    ("castigate" for "laud") often fits just as well grammatically.
    `avoid_terms` drops words that are, or list as a synonym, any of these
    strings (e.g. a synonym-pair partner that isn't itself a bank word).
    """
    group = lambda w: groups.get(w.cluster, w.cluster)  # noqa: E731
    excluded = {group(target)}
    if avoid_opposites:
        excluded |= {
            group(w) for w in pool
            if w.lemma in target.antonyms or target.lemma in w.antonyms
        }
    candidates = [
        w for w in pool
        if w.id != target.id and group(w) not in excluded and not related(w, target)
        and w.lemma not in avoid_terms and not avoid_terms & set(w.synonyms)
    ]
    rng.shuffle(candidates)

    def rank(w: Word) -> int:
        if w.id in confused_ids:
            return 0
        if w.lemma in target.confusables:
            return 1
        if prefer_pos and w.pos == target.pos:
            return 2
        return 3

    candidates.sort(key=rank)
    chosen, used = [], set()
    for w in candidates:
        if group(w) in used or any(related(w, c) for c in chosen):
            continue
        chosen.append(w)
        used.add(group(w))
        if len(chosen) == n:
            break
    return chosen


def _eliminate_two(item: IssuedItem) -> dict:
    correct = item.answer["index"]
    wrong = [i for i in range(len(item.payload["options"])) if i != correct]
    rng = random.Random(item.id)
    return {"eliminate": sorted(rng.sample(wrong, k=min(2, len(wrong))))}


def _single_choice_grade(item: IssuedItem, response: dict) -> Grade:
    selected = response.get("selected")
    correct_index = item.answer["index"]
    ok = selected == correct_index
    chosen = []
    if not ok and isinstance(selected, int) and 0 <= selected < len(item.answer["word_ids"]):
        wid = item.answer["word_ids"][selected]
        if wid is not None:
            chosen.append(wid)
    return Grade(
        correct=ok,
        score=1.0 if ok else 0.0,
        chosen_word_ids=chosen,
        feedback={"correct_index": correct_index},
    )


class Flashcard(ItemType):
    name, section = "flashcard", "verbal"

    def build(self, db, user_id, word: Word) -> BuiltItem:
        return BuiltItem(
            payload={"word": word.lemma, "pos": word.pos, "pronunciation": word.pronunciation}, answer={}
        )

    async def grade(self, db, item, response) -> Grade:
        rating = int(response.get("self_rating", 1))
        rating = min(4, max(1, rating))
        ok = rating >= 2
        return Grade(correct=ok, score=1.0 if ok else 0.0, self_rating=rating)


class Meaning(ItemType):
    name, section, hint_available = "meaning", "verbal", True

    def build(self, db, user_id, word: Word) -> BuiltItem | None:
        rng = random.Random()
        pool, groups = _pool(db)
        distractors = pick_distractors(
            word, pool, 3, groups=groups, confused_ids=_confused_ids(db, user_id, word.id), rng=rng
        )
        if len(distractors) < 3:
            return None
        options = [word] + distractors
        rng.shuffle(options)
        return BuiltItem(
            payload={
                "word": word.lemma,
                "pos": word.pos,
                "pronunciation": word.pronunciation,
                "prompt": f"Which best defines “{word.lemma}”?",
                "options": [w.definition for w in options],
            },
            answer={"index": options.index(word), "word_ids": [w.id for w in options]},
        )

    async def grade(self, db, item, response) -> Grade:
        return _single_choice_grade(item, response)

    def hint(self, item):
        return _eliminate_two(item)


class Cloze(ItemType):
    name, section, hint_available = "cloze", "verbal", True

    def build(self, db, user_id, word: Word) -> BuiltItem | None:
        rng = random.Random()
        pattern = re.compile(rf"\b{re.escape(word.lemma)}\b", re.IGNORECASE)
        usable = [s for s in word.examples if pattern.search(s)]
        if not usable:
            return None
        sentence = pattern.sub(BLANK, rng.choice(usable), count=1)
        pool, groups = _pool(db)
        distractors = pick_distractors(
            word, pool, 3, groups=groups,
            confused_ids=_confused_ids(db, user_id, word.id), prefer_pos=True,
            avoid_opposites=True, rng=rng,
        )
        if len(distractors) < 3:
            return None
        options = [word] + distractors
        rng.shuffle(options)
        return BuiltItem(
            payload={
                "prompt": "Choose the word that best completes the sentence.",
                "sentence": sentence,
                "options": [w.lemma for w in options],
            },
            answer={"index": options.index(word), "word_ids": [w.id for w in options]},
        )

    async def grade(self, db, item, response) -> Grade:
        return _single_choice_grade(item, response)

    def hint(self, item):
        return _eliminate_two(item)


class Synonyms(ItemType):
    """Six options, exactly one synonymous pair (the target and a near-synonym)."""

    name, section, hint_available = "synonyms", "verbal", True

    def build(self, db, user_id, word: Word) -> BuiltItem | None:
        rng = random.Random()
        pool, groups = _pool(db)
        mates = [w for w in pool if w.cluster == word.cluster and w.id != word.id]
        # Prefer mates the entries themselves list as synonyms: the closest pairs.
        mates = [w for w in mates if related(w, word)] or mates
        if mates:
            mate = rng.choice(mates)
            partner = (mate.lemma, mate.id)
        elif word.synonyms:
            partner = (word.synonyms[0], None)
        else:
            return None

        distractors = pick_distractors(
            word, pool, 4, groups=groups, confused_ids=_confused_ids(db, user_id, word.id),
            avoid_terms=frozenset({partner[0]}), rng=rng,
        )
        options = [(word.lemma, word.id), partner] + [(w.lemma, w.id) for w in distractors]
        # Swap in one look-alike that isn't in the bank (e.g. "energize" for "enervate"),
        # unless it happens to mean the same as one of the remaining options.
        bank_lemmas = {w.lemma for w in pool}
        kept_synonyms = {s for w in distractors[:-1] for s in w.synonyms}
        lookalikes = [
            c for c in word.confusables
            if c not in bank_lemmas and c not in kept_synonyms and c != partner[0]
        ]
        if lookalikes and len(options) == 6:
            options[-1] = (rng.choice(lookalikes), None)
        if len(options) < 6:
            return None

        rng.shuffle(options)
        labels = [o[0] for o in options]
        return BuiltItem(
            payload={
                "prompt": "Select the TWO words that are closest in meaning.",
                "options": labels,
            },
            answer={
                "indices": sorted([labels.index(word.lemma), labels.index(partner[0])]),
                "target_index": labels.index(word.lemma),
                "word_ids": [o[1] for o in options],
            },
        )

    async def grade(self, db, item, response) -> Grade:
        selected = response.get("selected") or []
        answer = item.answer["indices"]
        ok = sorted(selected) == answer
        word_ids = item.answer["word_ids"]
        chosen = [
            word_ids[i] for i in selected
            if isinstance(i, int) and 0 <= i < len(word_ids) and i not in answer and word_ids[i] is not None
        ]
        return Grade(
            correct=ok, score=1.0 if ok else 0.0, chosen_word_ids=chosen,
            feedback={"correct_indices": answer},
        )

    def hint(self, item):
        return {"reveal": item.answer["target_index"]}


class Usage(ItemType):
    name, section = "usage", "verbal"

    def build(self, db, user_id, word: Word) -> BuiltItem:
        return BuiltItem(
            payload={
                "word": word.lemma,
                "pos": word.pos,
                "pronunciation": word.pronunciation,
                "prompt": f"Write a sentence that uses “{word.lemma}” correctly "
                          "and makes its meaning clear from context.",
            },
            answer={},
        )

    async def grade(self, db, item, response) -> Grade:
        sentence = str(response.get("sentence", "")).strip()[:600]
        word = db.get(Word, item.word_id)
        stem = word.lemma.lower()[: max(4, len(word.lemma) - 2)]
        if len(sentence.split()) < 4 or stem not in sentence.lower():
            return Grade(
                correct=False, score=0.0,
                feedback={"ai_feedback": f"Write a full sentence that includes “{word.lemma}”."},
            )
        result = await claude.check_usage(word, sentence)
        return Grade(
            correct=bool(result["correct"]),
            score=result["score"],
            feedback={
                "ai_feedback": result["feedback"],
                "improved_sentence": result["improved_sentence"],
            },
        )


for _cls in (Flashcard, Meaning, Cloze, Synonyms, Usage):
    register(_cls())
