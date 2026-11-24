"""What's on screen, written out for the coach: the Vocab or Practice question
(with the student's answer once given, and what the coach may say before that)
or the word page being read."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, IssuedItem, Word
from app.services import practice
from app.services.ai import word_entry

# ---- the question on screen (Vocab study page) ----

LETTERS = "ABCDEF"
TYPE_LABEL = {
    "flashcard": "Flashcard (self-graded recall)",
    "meaning": "Multiple choice: pick the definition",
    "cloze": "Multiple choice: pick the word that completes the sentence",
    "synonyms": "Multiple choice: pick the TWO words closest in meaning",
    "usage": "Writing: use the word in a sentence (graded by AI)",
}

RULES_BEFORE_MCQ = """THE STUDENT HAS NOT ANSWERED YET. Coach, don't solve:
- Never say or hint at which option is correct, never rule options in or out,
  and never give the target word's definition or say which word fits.
- You may: clarify what the question asks, explain words in the sentence that
  aren't options, suggest a strategy, or give ONE partial clue that narrows the
  choice without settling it (the word's tone, positive or negative; a related
  word family; what kind of situation it describes). Don't translate a root
  into the definition: that is the answer.
- If they ask for the answer, say kindly that you'll go through everything as
  soon as they lock in an answer."""

RULES_BEFORE_USAGE = """THE STUDENT HAS NOT SUBMITTED A SENTENCE YET. You may explain the word's
meaning, nuance and typical contexts, but never write a sentence using the word
that they could submit. Comment on their ideas instead."""

RULES_FLASHCARD = """This is a self-graded flashcard, so talk about the word freely."""

RULES_AFTER = """The student has answered (see their answer below). Explain freely: why the
right answer is right, why their choice was or wasn't, and how to tell the
options apart next time."""

def _question_text(item: IssuedItem, word: Word) -> str:
    p, a = item.payload, item.answer
    lines = [f"Type: {TYPE_LABEL.get(item.item_type, item.item_type)}", f"Target word: {word.lemma}"]
    if p.get("prompt"):
        lines.append(f"Prompt: {p['prompt']}")
    if p.get("sentence"):
        lines.append(f"Sentence: {p['sentence']}")
    for i, opt in enumerate(p.get("options") or []):
        lines.append(f"  {LETTERS[i]}. {opt}")
    if "index" in a:
        lines.append(f"Correct answer: {LETTERS[a['index']]}")
    elif "indices" in a:
        lines.append("Correct answer: " + " and ".join(LETTERS[i] for i in a["indices"]))
    return "\n".join(lines)


def _student_answer(item: IssuedItem, attempt: Attempt) -> str:
    r = attempt.response or {}
    verdict = "correct" if attempt.correct else "incorrect"
    if item.item_type == "flashcard":
        return f"Self-rated {r.get('self_rating')} of 4 (1 = forgot, 4 = easy)."
    if item.item_type == "usage":
        return f"Sentence: {r.get('sentence', '')!r} ({verdict})."
    sel = r.get("selected")
    sel = sel if isinstance(sel, list) else [sel] if isinstance(sel, int) else []
    chosen = " and ".join(LETTERS[i] for i in sel if isinstance(i, int) and 0 <= i < len(LETTERS)) or "nothing"
    return f"Chose {chosen} ({verdict})."


def _rules(item: IssuedItem, answered: bool) -> str:
    if answered:
        return RULES_AFTER
    if item.item_type == "flashcard":
        return RULES_FLASHCARD
    return RULES_BEFORE_USAGE if item.item_type == "usage" else RULES_BEFORE_MCQ


# ---- the question on screen (Practice page) ----

RULES_BEFORE_PRACTICE = """THE STUDENT HAS NOT ANSWERED YET. Coach, don't solve:
- Never say or hint at which choice is correct, never rule choices in or out,
  never work the problem through to its answer or state a number that settles
  it, and never say which words fill the blanks.
- You may: clarify what the question asks, explain a concept, formula or GRE
  strategy it relies on (in general terms, with a different example), explain
  vocabulary in the text, or give the question's own hint (below) if they
  ask for a hint. Don't paraphrase the explanation: that is the answer.
- If they ask for the answer, say kindly that you'll go through everything as
  soon as they lock in an answer."""

RULES_AFTER_PRACTICE = """The student has answered (see their answer below). Explain freely: why the
right answer is right, where their reasoning may have gone wrong, and the
takeaway for similar questions. Use the explanation below as the answer key."""


def _choices(options: list[str]) -> list[str]:
    return [f"  {LETTERS[i]}. {o}" for i, o in enumerate(options)]


def _letters(indices: list[int]) -> str:
    return " and ".join(LETTERS[i] for i in indices if isinstance(i, int) and 0 <= i < len(LETTERS)) or "nothing"


def _practice_text(item: IssuedItem, kind_name: str) -> str:
    p, a = item.payload, item.answer
    lines = [f"Type: {kind_name} ({item.section}, {p.get('difficulty')})"]
    if p.get("topic"):
        lines.append(f"Topic: {p['topic']}")
    if item.item_type == "rc":
        lines += [f"Passage:\n{p['passage']}", f"Question {p['order']} of {p['of']} on this passage: {p['question']}"]
    elif item.item_type == "qc":
        if p.get("info"):
            lines.append(f"Given: {p['info']}")
        lines += [f"Quantity A: {p['quantity_a']}", f"Quantity B: {p['quantity_b']}"]
    else:
        lines.append(f"Question: {p['text']}")
    if p.get("table"):
        t = p["table"]
        lines.append("Table:\n" + "\n".join(" | ".join(map(str, r)) for r in [t["columns"], *t["rows"]]))
    if item.item_type == "tc":
        for b, opts in enumerate(p["blanks"]):
            lines.append(f"Blank ({'i' * (b + 1) if b < 3 else b + 1}):")
            lines += _choices(opts)
        lines.append("Correct answer: " + ", ".join(
            f"blank {b + 1}: {LETTERS[i]} ({p['blanks'][b][i]})" for b, i in enumerate(a["indices"])))
    elif item.item_type == "qne":
        lines.append(f"Numeric entry{' as a fraction' if p.get('fraction') else ''}"
                     f"{' in ' + p['unit'] if p.get('unit') else ''}.")
        lines.append(f"Correct answer: {a['value']}")
    else:
        if p.get("select") == "all":
            lines.append("Select all that apply.")
        elif item.item_type == "se":
            lines.append("Select the two words that complete the sentence with the same meaning.")
        lines += _choices(p["options"])
        lines.append(f"Correct answer: {_letters(a['indices'])}")
    lines += [f"The question's own hint: {a['clue']}", f"Explanation (answer key): {a['explanation']}"]
    return "\n".join(lines)


def _practice_answer(item: IssuedItem, attempt: Attempt) -> str:
    r = attempt.response or {}
    verdict = "correct" if attempt.correct else "incorrect"
    if item.item_type == "qne":
        return f"Entered {r.get('value')!r} ({verdict})."
    sel = r.get("selected") if isinstance(r.get("selected"), list) else []
    if item.item_type == "tc":
        picks = [f"blank {b + 1}: {LETTERS[i]}" for b, i in enumerate(sel)
                 if isinstance(i, int) and 0 <= i < len(LETTERS)]
        return f"Chose {', '.join(picks) or 'nothing'} ({verdict})."
    return f"Chose {_letters(sel)} ({verdict})."


def _page_context(db: Session, user_id: str, study_item_id: str | None, practice_item_id: str | None,
                  word_id: int | None):
    """What's on screen: (context text, extra rules, the question if any, whether it's answered)."""
    if practice_item_id:
        item = db.get(IssuedItem, practice_item_id)
        if item is None or item.user_id != user_id or item.bank_item_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
        attempt = db.scalar(select(Attempt).where(Attempt.item_id == item.id))
        text = (
            "The student is on the Practice page, working on this question:\n"
            f"<question>\n{_practice_text(item, practice.KIND_NAMES[item.item_type])}\n</question>\n\n"
            f"<student_answer>\n{_practice_answer(item, attempt) if attempt else 'Not answered yet.'}\n"
            "</student_answer>"
        )
        rules = "About this question:\n" + (RULES_AFTER_PRACTICE if attempt else RULES_BEFORE_PRACTICE)
        return text, rules, item, attempt is not None
    if study_item_id:
        item = db.get(IssuedItem, study_item_id)
        if item is None or item.user_id != user_id or item.word_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
        word = db.get(Word, item.word_id)
        attempt = db.scalar(select(Attempt).where(Attempt.item_id == item.id))
        text = (
            "The student is on the Vocab study page, working on this question:\n"
            f"<question>\n{_question_text(item, word)}\n</question>\n\n"
            f"<student_answer>\n{_student_answer(item, attempt) if attempt else 'Not answered yet.'}\n"
            f"</student_answer>\n\n<target_word_entry>\n{word_entry(word)}\n</target_word_entry>"
        )
        rules = "About this question:\n" + _rules(item, attempt is not None)
        return text, rules, item, attempt is not None
    if word_id is not None:
        word = db.get(Word, word_id)
        if word is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Word not found")
        text = (f"The student is reading the word page for “{word.lemma}”:\n"
                f"<word_entry>\n{word_entry(word)}\n</word_entry>")
        return text, "", None, False
    return "The student isn't looking at a particular question or word right now.", "", None, False
