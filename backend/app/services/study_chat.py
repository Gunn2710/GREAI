"""Tutor chat about the question the student is working on right now.

Claude sees the question exactly as shown, the answer key, and, once the
student has answered, what they chose. Until then it coaches without giving the
answer away. It can look things up with tools: any word's verified entry,
words matching a meaning, and the student's own record with this word.
"""
import json

from fastapi import HTTPException, status
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from app import engine_bridge as eb
from app.models import Attempt, Card, Confusion, IssuedItem, Word
from app.services.ai import TUTOR_SCOPE, claude, word_entry

MCQ_TYPES = ("meaning", "cloze", "synonyms")
LETTERS = "ABCDEF"
TYPE_LABEL = {
    "flashcard": "Flashcard (self-graded recall)",
    "meaning": "Multiple choice: pick the definition",
    "cloze": "Multiple choice: pick the word that completes the sentence",
    "synonyms": "Multiple choice: pick the TWO words closest in meaning",
    "usage": "Writing: use the word in a sentence (graded by AI)",
}

SYSTEM = """You are a friendly, sharp GRE vocabulary tutor sitting beside a student
during a study session. The question they are on, its answer key, and the
target word's verified entry are below. Treat the verified entries as the
source of truth; if you use your own knowledge, say so.

Use the tools when they help: look_up_word for any word's verified entry (the
options, a word the student mentions), find_words_by_meaning for related
words, and student_history before talking about their past mistakes or
progress. Don't mention the tools by name.

Keep replies short (under 120 words unless asked for more), concrete and
conversational. Plain text only: no markdown, so no asterisks, headings or tables.

{scope}

{rules}"""

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

TOOLS = [
    {
        "name": "look_up_word",
        "description": "Verified dictionary entry for a word in the app's GRE word bank: definition, "
                       "nuance, examples, synonyms, antonyms, commonly confused words. Use it for the "
                       "question's options or any word the student asks about.",
        "input_schema": {
            "type": "object",
            "properties": {"word": {"type": "string", "description": "The word, e.g. 'laconic'"}},
            "required": ["word"],
        },
    },
    {
        "name": "find_words_by_meaning",
        "description": "Search the word bank for words whose definition or synonyms contain a phrase, "
                       "e.g. 'praise' or 'stubborn'. Returns up to 8 words with short definitions.",
        "input_schema": {
            "type": "object",
            "properties": {"phrase": {"type": "string"}},
            "required": ["phrase"],
        },
    },
    {
        "name": "student_history",
        "description": "This student's record with the current word: comfort level, review stats, "
                       "recent attempts, and the words they have confused it with.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


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


class Tools:
    def __init__(self, db: Session, user_id: str, word: Word, item: IssuedItem):
        self.db, self.user_id, self.word, self.item = db, user_id, word, item

    def __call__(self, name: str, args: dict) -> str:
        if name == "look_up_word":
            return self.look_up_word(str(args.get("word", "")))
        if name == "find_words_by_meaning":
            return self.find_words_by_meaning(str(args.get("phrase", "")))
        if name == "student_history":
            return self.student_history()
        raise ValueError(f"unknown tool {name}")

    def look_up_word(self, lemma: str) -> str:
        w = self.db.scalar(select(Word).where(func.lower(Word.lemma) == lemma.strip().lower()))
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

    def student_history(self) -> str:
        card = self.db.get(Card, (self.user_id, self.word.id))
        attempts = self.db.scalars(
            select(Attempt).where(Attempt.user_id == self.user_id, Attempt.word_id == self.word.id)
            .order_by(Attempt.created_at.desc()).limit(10)
        ).all()
        confused = self.db.execute(
            select(Word.lemma, Confusion.count).join(Word, Word.id == Confusion.chosen_word_id)
            .where(Confusion.user_id == self.user_id, Confusion.target_word_id == self.word.id)
            .order_by(Confusion.count.desc()).limit(5)
        ).all()
        return json.dumps({
            "word": self.word.lemma,
            "card": eb.card_summary(card, eb.now_days()) if card else None,
            "recent_attempts": [
                {"type": a.item_type, "correct": a.correct, "when": a.created_at.date().isoformat(),
                 "this_question": a.item_id == self.item.id}
                for a in attempts
            ],
            "confused_with": [{"word": lemma, "times": n} for lemma, n in confused],
            "note": "Attempts and confusion counts include the answer to the current question, if given.",
        }, default=str)


async def chat(db: Session, user_id: str, item_id: str, history: list[dict]) -> dict:
    item = db.get(IssuedItem, item_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    word = db.get(Word, item.word_id)
    attempt = db.scalar(select(Attempt).where(Attempt.item_id == item.id))
    answered = attempt is not None

    context = (
        f"<question>\n{_question_text(item, word)}\n</question>\n\n"
        f"<student_answer>\n{_student_answer(item, attempt) if answered else 'Not answered yet.'}\n</student_answer>\n\n"
        f"<target_word_entry>\n{word_entry(word)}\n</target_word_entry>"
    )
    system = SYSTEM.format(scope=TUTOR_SCOPE, rules=_rules(item, answered)) + "\n\n" + context
    reply = await claude.run_agent(system, history[-20:], TOOLS, Tools(db, user_id, word, item))

    # Help before answering is a hint as far as scheduling is concerned.
    counted_as_hint = not answered and item.item_type != "flashcard"
    if counted_as_hint and not item.hint_used:
        item.hint_used = True
        db.commit()
    return {"reply": reply, "counted_as_hint": counted_as_hint}
