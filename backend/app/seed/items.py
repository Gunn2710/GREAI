"""Load, validate and sync stored question banks (app/seed/verbal/, app/seed/quant/) into `items`.

Authoring conventions (each file's `_format` says the same):
  Verbal: the FIRST option of each blank (Text Completion), the FIRST TWO
  options (Sentence Equivalence) and the first option(s) of each Reading
  Comprehension question are correct; options are shuffled when served.
  Reading Comprehension is authored as passages, each with its questions;
  every question becomes its own item carrying the passage text.
  Quant: answers are stated explicitly and options keep their order.
Syncing matches items by slug and never deletes.
"""
import json
import re
from fractions import Fraction
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item, Skill

SEED_DIR = Path(__file__).parent

DIFFICULTY_PRIOR = {"easy": -0.5, "medium": 0.3, "hard": 1.0}

SKILLS = [
    ("verbal.tc", "verbal", "verbal", "Text Completion"),
    ("verbal.se", "verbal", "verbal", "Sentence Equivalence"),
    ("verbal.rc", "verbal", "verbal", "Reading Comprehension"),
    ("quant.qc", "quant", "quant", "Quantitative Comparison"),
    ("quant.qmc", "quant", "quant", "Multiple Choice"),
    ("quant.qne", "quant", "quant", "Numeric Entry"),
]

# kind -> (file under app/seed/, skill id, section)
BANKS = {
    "tc": ("verbal/text_completion.json", "verbal.tc", "verbal"),
    "se": ("verbal/sentence_equivalence.json", "verbal.se", "verbal"),
    "rc": ("verbal/reading_comprehension.json", "verbal.rc", "verbal"),
    "qc": ("quant/comparison.json", "quant.qc", "quant"),
    "qmc": ("quant/multiple_choice.json", "quant.qmc", "quant"),
    "qne": ("quant/numeric_entry.json", "quant.qne", "quant"),
}

QUANT_TOPICS = {"arithmetic", "algebra", "geometry", "data"}
QC_ANSWERS = "ABCD"

BLANK = re.compile(r"\{(\d)\}")


def parse_number(text: str) -> Fraction | None:
    """An integer, decimal or fraction ("1,200", "-0.5", "4/36") as an exact value."""
    try:
        return Fraction(str(text).replace(",", "").replace("−", "-").replace(" ", ""))
    except (ValueError, ZeroDivisionError):
        return None


def _flatten_passages(passages: list[dict]) -> list[dict]:
    """One item per Reading Comprehension question, each carrying its passage."""
    items = []
    for p in passages:
        for n, q in enumerate(p.get("questions", []), 1):
            items.append({**q, "passage_slug": p.get("slug", "?"), "passage": p.get("text", ""),
                          "topic": p.get("topic", ""), "order": n, "of": len(p["questions"])})
    return items


def load_items(directory: Path = SEED_DIR) -> dict[str, list[dict]]:
    banks = {}
    for kind, (filename, _, _) in BANKS.items():
        data = json.loads((directory / filename).read_text())
        banks[kind] = _flatten_passages(data["passages"]) if kind == "rc" else data["items"]
    return banks


def _distinct(opts) -> bool:
    return isinstance(opts, list) and all(isinstance(o, str) and o.strip() for o in opts) and len(set(opts)) == len(opts)


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
            if kind in ("rc", "qc", "qmc", "qne"):
                problems += [f"{slug}: {p}" for p in _check_new_kinds(kind, it)]
                continue
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


def _check_new_kinds(kind: str, it: dict) -> list[str]:
    problems = []
    if kind == "rc":
        if not it.get("passage", "").strip() or not it.get("question", "").strip():
            problems.append("needs a passage and a question")
        opts = it.get("options", [])
        if it.get("select") == "one":
            if len(opts) != 5 or not _distinct(opts):
                problems.append("a select-one question needs 5 distinct options")
        elif it.get("select") == "all":
            if len(opts) != 3 or not _distinct(opts):
                problems.append("a select-all question needs 3 distinct options")
            if it.get("correct") not in (1, 2, 3):
                problems.append("a select-all question needs correct = 1, 2 or 3")
        else:
            problems.append('select must be "one" or "all"')
        return problems

    if it.get("topic") not in QUANT_TOPICS:
        problems.append(f"topic must be one of {sorted(QUANT_TOPICS)}")
    table = it.get("table")
    if table is not None:
        cols = table.get("columns", [])
        if not cols or any(len(r) != len(cols) for r in table.get("rows", [])) or not table.get("rows"):
            problems.append("table needs columns and rows of the same width")
    if kind == "qc":
        if not it.get("quantity_a", "").strip() or not it.get("quantity_b", "").strip():
            problems.append("needs quantity_a and quantity_b")
        if it.get("answer") not in tuple(QC_ANSWERS):
            problems.append("answer must be A, B, C or D")
    elif kind == "qmc":
        opts, answer = it.get("options", []), it.get("answer", [])
        if not it.get("text", "").strip():
            problems.append("needs text")
        if not _distinct(opts):
            problems.append("options must be distinct")
        if not isinstance(answer, list) or not answer or len(set(answer)) != len(answer) \
                or any(not isinstance(a, int) or not 0 <= a < len(opts) for a in answer):
            problems.append("answer must list valid option indices")
        if it.get("select") == "one":
            if len(opts) != 5 or len(answer) != 1:
                problems.append("a select-one question needs 5 options and one answer")
        elif it.get("select") == "all":
            if not 3 <= len(opts) <= 8:
                problems.append("a select-all question needs 3-8 options")
        else:
            problems.append('select must be "one" or "all"')
    else:  # qne
        if not it.get("text", "").strip():
            problems.append("needs text")
        if parse_number(it.get("answer", "")) is None:
            problems.append("answer must be a number or fraction")
        elif it.get("fraction") and "/" not in it["answer"]:
            problems.append("a fraction question's answer must be written as a fraction")
    return problems


def sync_items(db: Session, directory: Path = SEED_DIR) -> dict:
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
        _, skill_id, section = BANKS[kind]
        for it in items:
            content = {k: v for k, v in it.items() if k not in ("slug", "difficulty")}
            values = {
                "section": section, "item_type": kind, "skill_id": skill_id,
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
