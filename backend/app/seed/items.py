"""Load, validate and sync stored question banks (app/seed/verbal/) into `items`.

Authoring convention: the FIRST option of each blank (Text Completion) and the
FIRST TWO options (Sentence Equivalence) are correct. Options are shuffled when
a question is served. Syncing matches items by slug and never deletes.
"""
import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item, Skill

VERBAL_DIR = Path(__file__).with_name("verbal")

DIFFICULTY_PRIOR = {"easy": -0.5, "medium": 0.3, "hard": 1.0}

SKILLS = [
    ("verbal.tc", "verbal", "verbal", "Text Completion"),
    ("verbal.se", "verbal", "verbal", "Sentence Equivalence"),
]

BANKS = {
    "tc": ("text_completion.json", "verbal.tc"),
    "se": ("sentence_equivalence.json", "verbal.se"),
}

BLANK = re.compile(r"\{(\d)\}")


def load_items(directory: Path = VERBAL_DIR) -> dict[str, list[dict]]:
    return {
        kind: json.loads((directory / filename).read_text())["items"]
        for kind, (filename, _) in BANKS.items()
    }


def validate_items(banks: dict[str, list[dict]]) -> list[str]:
    problems: list[str] = []
    slugs: set[str] = set()
    for kind, items in banks.items():
        for it in items:
            slug = it.get("slug", "?")
            if slug in slugs:
                problems.append(f"{slug}: duplicate slug")
            slugs.add(slug)
            if it.get("difficulty") not in DIFFICULTY_PRIOR:
                problems.append(f"{slug}: difficulty must be easy, medium or hard")
            if not it.get("explanation") or not it.get("clue"):
                problems.append(f"{slug}: needs a clue and an explanation")
            markers = [int(m) for m in BLANK.findall(it.get("text", ""))]

            if kind == "tc":
                blanks = it.get("blanks", [])
                if not 1 <= len(blanks) <= 3 or markers != list(range(1, len(blanks) + 1)):
                    problems.append(f"{slug}: text must contain {{1}}..{{n}} once each for 1-3 blanks")
                size = 5 if len(blanks) == 1 else 3
                for i, opts in enumerate(blanks, 1):
                    if len(opts) != size or len(set(opts)) != size:
                        problems.append(f"{slug}: blank {i} needs {size} distinct options")
            else:
                opts = it.get("options", [])
                if markers != [1]:
                    problems.append(f"{slug}: text must contain {{1}} exactly once")
                if len(opts) != 6 or len(set(opts)) != 6:
                    problems.append(f"{slug}: needs 6 distinct options")
    return problems


def sync_items(db: Session, directory: Path = VERBAL_DIR) -> dict:
    banks = load_items(directory)
    problems = validate_items(banks)
    if problems:
        raise ValueError("Question bank failed validation:\n  " + "\n  ".join(problems))

    for sid, section, parent, name in SKILLS:
        if db.get(Skill, sid) is None:
            db.add(Skill(id=sid, section=section, parent_id=parent, name=name))
    db.flush()

    existing = {i.slug: i for i in db.scalars(select(Item))}
    added = updated = 0
    for kind, items in banks.items():
        skill_id = BANKS[kind][1]
        for it in items:
            content = {k: v for k, v in it.items() if k not in ("slug", "difficulty")}
            values = {
                "section": "verbal", "item_type": kind, "skill_id": skill_id,
                "difficulty_label": it["difficulty"],
                "difficulty_prior": DIFFICULTY_PRIOR[it["difficulty"]],
                "content": content,
            }
            row = existing.get(it["slug"])
            if row is None:
                db.add(Item(slug=it["slug"], **values))
                added += 1
            elif any(getattr(row, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(row, k, v)
                updated += 1
    db.commit()
    return {"added": added, "updated": updated, "total": sum(len(v) for v in banks.values())}
