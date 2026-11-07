"""Load and sync the vocabulary bank (app/seed/vocab/) into the database.

    vocab/clusters.json   tiers, frequency sources, families, clusters
    vocab/words_*.json    word entries

Clusters group near-synonyms. Families group clusters whose meanings are close
enough to be confused (e.g. "soothe" and "ease"); quiz distractors never come
from the target's own family. Syncing is idempotent: new words are inserted,
existing ones (matched by lemma) are updated, and nothing is deleted.

Words are split into study sets of 20-30 (see assign_sets): the most common
words first, so working through the sets in order is the progression.
"""
import hashlib
import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Skill, Word

log = logging.getLogger(__name__)

VOCAB_DIR = Path(__file__).with_name("vocab")
VOCAB_ROOT = "verbal.vocab"
FAMILY_PREFIX = f"{VOCAB_ROOT}.family."

ROOT_SKILLS = [
    ("verbal", "verbal", None, "Verbal Reasoning"),
    (VOCAB_ROOT, "verbal", "verbal", "Vocabulary"),
    ("quant", "quant", None, "Quantitative Reasoning"),
    ("writing", "writing", None, "Analytical Writing"),
]

WORD_FIELDS = ("pos", "pronunciation", "definition", "nuance", "phrases", "examples", "synonyms", "antonyms", "confusables", "cluster", "tier")


# Respelling: hyphenated lowercase syllables with exactly one CAPITALIZED
# (stressed) syllable; accepted variants joined by " or ".
SYLLABLE = r"(?:[a-z]+|[A-Z]+)"
RESPELLING = re.compile(rf"^{SYLLABLE}(?:-{SYLLABLE})*$")


def valid_pronunciation(value: str | None) -> bool:
    if not value:
        return False
    for variant in value.split(" or "):
        syllables = variant.split("-")
        if not RESPELLING.match(variant) or sum(s.isupper() for s in syllables) != 1:
            return False
    return True


def inflections(lemma: str) -> set[str]:
    """The lemma plus its regular inflections (plural, -s, -ed, -ing)."""
    forms = {lemma, lemma + "s", lemma + "es", lemma + "d", lemma + "ed", lemma + "ing"}
    forms |= {lemma + lemma[-1] + "ed", lemma + lemma[-1] + "ing"}  # extolled
    if lemma.endswith("e"):
        forms.add(lemma[:-1] + "ing")
    if lemma.endswith("y") and lemma[-2] not in "aeiou":
        forms |= {lemma[:-1] + "ies", lemma[:-1] + "ied"}
    return forms


def load_bank(directory: Path = VOCAB_DIR) -> tuple[dict, list[dict]]:
    meta = json.loads((directory / "clusters.json").read_text())
    words: list[dict] = []
    for path in sorted(directory.glob("words_*.json")):
        words.extend(json.loads(path.read_text())["words"])
    return meta, words


def validate_bank(meta: dict, words: list[dict]) -> list[str]:
    """Data-quality rules the quiz generator depends on."""
    problems: list[str] = []
    clusters, families = meta["clusters"], meta["families"]
    by_lemma: dict[str, dict] = {}
    for w in words:
        if w["lemma"] in by_lemma:
            problems.append(f"{w['lemma']}: duplicate lemma")
        by_lemma[w["lemma"]] = w

    def group(w: dict) -> str:
        return clusters[w["cluster"]].get("family") or w["cluster"]

    for key, c in clusters.items():
        if c.get("family") and c["family"] not in families:
            problems.append(f"cluster {key}: unknown family {c['family']!r}")
    used = {w["cluster"] for w in words}
    problems += [f"cluster {k}: has no words" for k in clusters if k not in used]

    for w in words:
        lemma = w["lemma"]
        if w["cluster"] not in clusters:
            problems.append(f"{lemma}: unknown cluster {w['cluster']!r}")
            continue
        if w.get("tier") not in (1, 2, 3):
            problems.append(f"{lemma}: tier must be 1, 2 or 3")
        if w.get("freq_source", "editorial") not in meta["freq_sources"]:
            problems.append(f"{lemma}: unknown freq_source")
        pattern = re.compile(rf"\b{re.escape(lemma)}\b", re.IGNORECASE)
        if len(w["examples"]) < 2 or not all(pattern.search(s) for s in w["examples"]):
            problems.append(f"{lemma}: needs 2+ examples that each contain the exact lemma")
        # Phrases are the word in its most common real-world combinations, so
        # each one must use the word itself (or a regular inflection of it).
        phrases = w.get("phrases", [])
        form = re.compile(r"\b(?:" + "|".join(map(re.escape, inflections(lemma))) + r")\b", re.IGNORECASE)
        if not 2 <= len(phrases) <= 4 or not all(form.search(p) for p in phrases):
            problems.append(f"{lemma}: needs 2-4 common phrases that each use the word")
        if len(set(phrases)) != len(phrases):
            problems.append(f"{lemma}: duplicate phrase")
        if not valid_pronunciation(w.get("pronunciation")):
            problems.append(f"{lemma}: needs a pronunciation like \"luh-KAH-nik\" (one CAPITAL stressed syllable)")
        if not w["synonyms"]:
            problems.append(f"{lemma}: needs at least one synonym")
        if len(set(w["synonyms"])) != len(w["synonyms"]):
            problems.append(f"{lemma}: duplicate synonym")
        if lemma in w["synonyms"]:
            problems.append(f"{lemma}: lists itself as a synonym")
        if set(w["confusables"]) & set(w["synonyms"]):
            problems.append(f"{lemma}: a confusable is also a synonym")
        # A synonym that is itself a bank word must be in the same cluster or
        # family; otherwise synonym-pair questions could have two right answers.
        for s in w["synonyms"]:
            other = by_lemma.get(s)
            if other and other["cluster"] in clusters and group(other) != group(w):
                problems.append(f"{lemma}: synonym {s!r} is in unrelated cluster {other['cluster']!r}")
    return problems


SET_SIZE = 25  # target; every set gets 20-30 words when its tier has enough
MAX_SET_SIZE = 30
TOP_SOURCE = "magoosh_top20"  # the most-tested words open the first set


def _stable_key(text: str) -> str:
    """A fixed pseudo-random order, the same on every machine and every sync."""
    return hashlib.sha1(text.encode()).hexdigest()


def _study_order(words: list[dict]) -> list[dict]:
    """The most-tested words first, then the rest with each cluster's words
    spread evenly through the order, so near-synonyms land in different sets
    (they are harder to learn together)."""
    top = sorted((w for w in words if w.get("freq_source") == TOP_SOURCE), key=lambda w: _stable_key(w["lemma"]))
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for w in words:
        if w.get("freq_source") != TOP_SOURCE:
            by_cluster[w["cluster"]].append(w)
    placed = []
    for cluster, ws in by_cluster.items():
        offset = int(_stable_key(cluster)[:8], 16) / 16**8  # where in its slot the cluster starts
        for j, w in enumerate(sorted(ws, key=lambda w: _stable_key(w["lemma"]))):
            placed.append(((j + offset) / len(ws), _stable_key(w["lemma"]), w))
    return top + [w for *_, w in sorted(placed, key=lambda x: x[:2])]


def _set_count(n: int) -> int:
    if n == 0:
        return 0
    count = max(1, round(n / SET_SIZE))
    while n / count > MAX_SET_SIZE:
        count += 1
    return count


def assign_sets(words: list[dict]) -> dict[str, tuple[int, int]]:
    """lemma -> (set number, rank in the whole study order). Sets never mix
    frequency tiers; each tier is split into near-equal sets of about 25."""
    by_tier: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        by_tier[w["tier"]].append(w)
    out: dict[str, tuple[int, int]] = {}
    set_no = rank = 0
    for tier in sorted(by_tier):
        ordered = _study_order(by_tier[tier])
        count = _set_count(len(ordered))
        for i in range(count):
            set_no += 1
            chunk = ordered[round(i * len(ordered) / count):round((i + 1) * len(ordered) / count)]
            for w in chunk:
                rank += 1
                out[w["lemma"]] = (set_no, rank)
    return out


def _upsert_skill(db: Session, sid: str, section: str, parent: str | None, name: str) -> None:
    skill = db.get(Skill, sid)
    if skill is None:
        db.add(Skill(id=sid, section=section, parent_id=parent, name=name))
    else:
        skill.parent_id, skill.name = parent, name


def sync_bank(db: Session, directory: Path = VOCAB_DIR) -> dict:
    meta, words = load_bank(directory)
    problems = validate_bank(meta, words)
    if problems:
        raise ValueError("Vocabulary bank failed validation:\n  " + "\n  ".join(problems))

    for sid, section, parent, name in ROOT_SKILLS:
        _upsert_skill(db, sid, section, parent, name)
    db.flush()
    for key, name in meta["families"].items():
        _upsert_skill(db, f"{FAMILY_PREFIX}{key}", "verbal", VOCAB_ROOT, name)
    db.flush()
    for key, c in meta["clusters"].items():
        parent = f"{FAMILY_PREFIX}{c['family']}" if c.get("family") else VOCAB_ROOT
        _upsert_skill(db, f"{VOCAB_ROOT}.{key}", "verbal", parent, c["label"])
    db.flush()

    existing = {w.lemma: w for w in db.scalars(select(Word))}
    sets = assign_sets(words)
    added = updated = 0
    for entry in words:
        values = {f: entry.get(f) for f in WORD_FIELDS}
        values["nuance"] = values["nuance"] or None
        values["skill_id"] = f"{VOCAB_ROOT}.{entry['cluster']}"
        values["set_no"], values["set_rank"] = sets[entry["lemma"]]
        row = existing.get(entry["lemma"])
        if row is None:
            db.add(Word(lemma=entry["lemma"], **values))
            added += 1
        elif any(getattr(row, k) != v for k, v in values.items()):
            for k, v in values.items():
                setattr(row, k, v)
            updated += 1
    db.commit()

    missing = set(existing) - {w["lemma"] for w in words}
    if missing:
        log.warning("Words in the database but not in the bank files (kept): %s", sorted(missing))
    return {"added": added, "updated": updated, "total": len(words)}


def cluster_groups(db: Session) -> dict[str, str]:
    """cluster key -> confusion group (its family, or the cluster itself)."""
    groups = {}
    prefix = f"{VOCAB_ROOT}."
    for skill in db.scalars(select(Skill).where(Skill.id.like(f"{prefix}%"))):
        if skill.id.startswith(FAMILY_PREFIX):
            continue
        key = skill.id[len(prefix):]
        parent = skill.parent_id or ""
        groups[key] = parent[len(FAMILY_PREFIX):] if parent.startswith(FAMILY_PREFIX) else key
    return groups
