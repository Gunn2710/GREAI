"""The study coach: the home page chat, and the chat bubble on every other page.

Claude sees a snapshot of the student's progress (plan, vocabulary, practice,
recent activity) and can look further with tools. It also knows what is on
screen: the Vocab or Practice question being worked on (it won't give the
answer away before the student answers) or the word page being read.

It can offer to do things (bring words back for review, mark a word known,
change study settings, save the student's sentence, open a practice type) but
never does them itself: each one is shown with a button the student clicks.
It keeps short notes about the student between chats, which they can delete.

The stable instructions and tool definitions are cached; what changes each
turn (the snapshot, the page, the notes) goes in a system message after the
student's latest message, so earlier turns stay cached too.
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CoachMessage
from app.services import limits
from app.services.ai import claude
from app.services.coach.page import _page_context
from app.services.coach.prompts import COACH_SCOPE, SYSTEM, TOOL_STATUS, TOOLS
from app.services.coach.tools import Tools, delete_note, notes, plan_of, snapshot
from app.services.study import get_profile

__all__ = ["chat", "chat_events", "check_page", "clear", "delete_note", "history", "notes"]

# Each student's chat is kept so it survives a refresh: the latest KEEP messages
# are shown, and the latest SENT of those go to Claude with each new question.
KEEP = 100
SENT = 20


def history(db: Session, user_id: str) -> list[dict]:
    """The student's saved chat, oldest first."""
    rows = db.scalars(
        select(CoachMessage).where(CoachMessage.user_id == user_id).order_by(CoachMessage.id.desc()).limit(KEEP)
    ).all()
    return [{"role": m.role, "content": m.content, "proposal": m.proposal, "actions": m.actions or []}
            for m in reversed(rows)]


def clear(db: Session, user_id: str) -> None:
    """Start a new chat."""
    db.query(CoachMessage).filter(CoachMessage.user_id == user_id).delete()
    db.commit()


def _save(db: Session, user_id: str, question: str, reply: str, proposal: dict | None,
          actions: list[dict]) -> None:
    db.add_all([
        CoachMessage(user_id=user_id, role="user", content=question),
        CoachMessage(user_id=user_id, role="assistant", content=reply, proposal=proposal,
                     actions=actions or None),
    ])
    db.flush()
    # Drop what's beyond the latest KEEP messages.
    cutoff = db.scalar(
        select(CoachMessage.id).where(CoachMessage.user_id == user_id)
        .order_by(CoachMessage.id.desc()).offset(KEEP - 1).limit(1)
    )
    if cutoff is not None:
        db.query(CoachMessage).filter(CoachMessage.user_id == user_id, CoachMessage.id < cutoff).delete()
    db.commit()


def _trim(history: list[dict]) -> list[dict]:
    """The latest messages, starting with one from the student."""
    recent = [{"role": m["role"], "content": m["content"]} for m in history[-SENT:]]
    while recent and recent[0]["role"] != "user":
        recent = recent[1:]
    return recent


def check_page(db: Session, user_id: str, study_item_id: str | None = None,
               practice_item_id: str | None = None, word_id: int | None = None) -> None:
    """Raise 404 for a page the student can't ask about (before a streamed reply starts)."""
    _page_context(db, user_id, study_item_id, practice_item_id, word_id)


def _context(db: Session, user_id: str, page: str, rules: str) -> str:
    """What changes from turn to turn: sent as a system message after the student's message."""
    kept = notes(db, user_id)
    note_lines = "\n".join(f"[{n['id']}] {n['text']}" for n in kept) or "No notes yet."
    return (
        (f"{rules}\n\n" if rules else "")
        + "Earlier messages may be about other pages or questions; this is what's on screen now:\n"
        + page
        + f"\n\n<progress_snapshot>\n{json.dumps(snapshot(db, user_id), indent=1)}\n</progress_snapshot>"
        + f"\n\n<your_notes_about_the_student>\n{note_lines}\n</your_notes_about_the_student>"
    )


async def chat_events(db: Session, user_id: str, message: str, study_item_id: str | None = None,
                      practice_item_id: str | None = None, word_id: int | None = None):
    """Answer the student's new message, continuing their saved chat, and save both.

    Yields events as the reply is written: {"type": "text", "text": ...} pieces,
    {"type": "status", "text": ...} while a tool runs, and finally {"type": "done", ...}
    with the whole reply, any plan proposal and offered actions, and requests left today.
    """
    page, rules, item, answered = _page_context(db, user_id, study_item_id, practice_item_id, word_id)
    thread = [
        *_trim([*history(db, user_id), {"role": "user", "content": message}]),
        {"role": "system", "content": _context(db, user_id, page, rules)},
    ]
    tools = Tools(db, user_id)
    reply = ""
    with limits.metered(db, user_id):
        async for kind, value in claude.agent(SYSTEM.format(scope=COACH_SCOPE), thread, TOOLS, tools,
                                              max_steps=6):
            if kind == "text":
                yield {"type": "text", "text": value}
            elif kind == "tool" and value in TOOL_STATUS:
                yield {"type": "status", "text": TOOL_STATUS[value]}
            elif kind == "reply":
                reply = value

    # Help with a question before answering it counts as a hint (for scheduling and ratings).
    counted_as_hint = item is not None and not answered and item.item_type != "flashcard"
    if counted_as_hint and not item.hint_used:
        item.hint_used = True
        db.commit()
    proposal = None
    if tools.proposal:
        proposal = {"changes": tools.proposal, "current": plan_of(get_profile(db, user_id))}
    _save(db, user_id, message, reply, proposal, tools.actions)
    yield {"type": "done", "reply": reply, "counted_as_hint": counted_as_hint, "proposal": proposal,
           "actions": tools.actions, "remaining": limits.remaining(db, user_id)}


async def chat(db: Session, user_id: str, message: str, **page) -> dict:
    """The whole reply at once (see chat_events)."""
    done = {}
    async for event in chat_events(db, user_id, message, **page):
        done = event
    done.pop("type", None)
    return done
