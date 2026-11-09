"""Offline content pipeline: generate word entries with Claude, then verify them.

    python scripts/generate_words.py lemmas.txt -o generated.json

Each lemma goes through:
  1. generate  - a full entry (definition, nuance, phrases, examples, synonyms, ...)
  2. verify    - a separate review that checks accuracy and flags problems
  3. revise    - only if the review or the automatic checks found problems:
                 the entry is rewritten to fix them, then verified once more
The automatic checks are the bank's own rules (every example contains the
exact lemma, which cloze items need; phrases use the word; a stress-marked
pronunciation). Results are saved as they finish, so an interrupted run picks
up where it stopped when started again with the same output file.

Review `generated.json`, then copy accepted entries into a new
app/seed/vocab/words_*.json file; the server validates and syncs it on the
next start.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.secrets_config import get_secrets  # noqa: E402
from app.seed.seed import inflections, valid_pronunciation  # noqa: E402

MODEL = "claude-opus-5-5"
FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
VOCAB_DIR = Path(__file__).parents[1] / "app/seed/vocab"

ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "lemma": {"type": "string"},
        "pos": {"type": "string", "enum": ["noun", "verb", "adjective", "adverb"]},
        "pronunciation": {"type": "string"},
        "definition": {"type": "string"},
        "nuance": {"type": "string"},
        "phrases": {"type": "array", "items": {"type": "string"}},
        "examples": {"type": "array", "items": {"type": "string"}},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "antonyms": {"type": "array", "items": {"type": "string"}},
        "confusables": {"type": "array", "items": {"type": "string"}},
        "cluster": {"type": "string"},
        "cluster_label": {"type": "string"},
        "family": {"type": "string"},
        "tier": {"type": "integer", "enum": [1, 2, 3]},
    },
    "required": ["lemma", "pos", "pronunciation", "definition", "nuance", "phrases", "examples", "synonyms",
                 "antonyms", "confusables", "cluster", "cluster_label", "family", "tier"],
    "additionalProperties": False,
}

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "accurate": {"type": "boolean"},
        "problems": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["accurate", "problems"],
    "additionalProperties": False,
}

ENTRY_RULES = """Requirements:
- pos: the part of speech of the sense most tested on the GRE.
- pronunciation: American English respelling, hyphenated lowercase syllables
  with the stressed syllable in CAPITALS, e.g. "luh-KAH-nik"; join accepted
  variants with " or ". Use: ah (hot), aw (law), uh (about), ih (sit),
  ee (see), ay (day), y/eye (by), oo (food), yoo (use), oh (go).
- definition: the sense most tested on the GRE, in plain words, lowercase, no
  trailing period; verbs start with "to". If the word has a second sense that
  is also tested, add it after a semicolon. Write it in your own words.
- nuance: one sentence on connotation or how it differs from near-synonyms.
- phrases: 2-4 of the word's most common real-world combinations, each using
  the word itself or a regular inflection (-s, -ed, -ing), e.g. for "laud":
  "widely lauded", "laud someone for something". Never a derived form
  ("laudable") or a phrase without the word.
- examples: 3 natural sentences in a GRE register. Each must contain the exact
  form "{lemma}" (not an inflection) and make its meaning clear from context.
- synonyms / antonyms: 2-3 single words or short phrases each, true for the
  tested sense. Never the word itself.
- confusables: words students mix it up with because they look or sound alike
  (empty if none). Never list synonyms here.
- cluster: one lowercase key for its meaning group, from the list below when
  one fits that meaning closely. Words in one cluster must be near-synonyms.
{hint}  If none fits, make a new key (lowercase, underscores) and give
  cluster_label (e.g. "To praise", "Stubborn") and family (one of the family
  keys below if the new cluster is close in meaning to it, else ""). For an
  existing cluster, leave cluster_label and family as "".
- tier: 1 = very common on the GRE, 2 = common, 3 = rare.

Existing clusters (key: label [family]):
{clusters}

Families (key: label):
{families}"""

GENERATE_PROMPT = """Write a GRE vocabulary entry for the word "{lemma}".

""" + ENTRY_RULES

VERIFY_PROMPT = """You are checking a GRE vocabulary entry written by someone else.
Flag anything a careful lexicographer would object to: a wrong or misleading
definition, a missing commonly tested sense, an example that misuses the word,
a phrase that isn't a real, common combination, a "synonym" that is not one,
a "confusable" that is actually related in meaning, or a wrong pronunciation.
Don't flag style preferences; mark accurate=false only for real errors.

<entry>
{entry}
</entry>"""

REVISE_PROMPT = """Here is a GRE vocabulary entry for "{lemma}" and the problems a reviewer
found in it. Rewrite the entry so that every problem is fixed, keeping what
was right. Keep the same cluster unless a problem is about the cluster.

<entry>
{entry}
</entry>

<problems>
{problems}
</problems>

""" + ENTRY_RULES


def text_of(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


class Usage:
    def __init__(self) -> None:
        self.input = self.output = self.calls = 0

    def add(self, response) -> None:
        self.calls += 1
        self.input += response.usage.input_tokens
        self.output += response.usage.output_tokens


async def call(client, usage: Usage, prompt: str, schema: dict, effort: str) -> dict:
    response = await client.beta.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        **FALLBACK,
    )
    usage.add(response)
    if response.stop_reason == "refusal":
        raise RuntimeError("refused")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("ran out of tokens")
    return json.loads(text_of(response))


def auto_checks(entry: dict, lemma: str) -> list[str]:
    problems = []
    if entry["lemma"].lower() != lemma.lower():
        problems.append(f"lemma changed to {entry['lemma']!r}; it must be {lemma!r}")
    pattern = re.compile(rf"\b{re.escape(lemma)}\b", re.IGNORECASE)
    missing = [s for s in entry["examples"] if not pattern.search(s)]
    if missing or len(entry["examples"]) < 2:
        problems.append(f"every example must contain the exact form {lemma!r}: {missing}")
    form = re.compile(r"\b(?:" + "|".join(map(re.escape, inflections(lemma))) + r")\b", re.IGNORECASE)
    phrases = entry["phrases"]
    if not 2 <= len(phrases) <= 4 or not all(form.search(p) for p in phrases) or len(set(phrases)) != len(phrases):
        problems.append("phrases: 2-4 distinct phrases, each using the word itself or a regular inflection")
    if not valid_pronunciation(entry.get("pronunciation")):
        problems.append("pronunciation must be hyphenated syllables with exactly one CAPITALIZED stressed syllable")
    if not entry["synonyms"] or lemma in entry["synonyms"] or len(set(entry["synonyms"])) != len(entry["synonyms"]):
        problems.append("synonyms: at least one, no duplicates, never the word itself")
    if set(entry["confusables"]) & set(entry["synonyms"]):
        problems.append("a confusable is also listed as a synonym")
    return problems


def bank_context() -> tuple[dict, list[dict]]:
    meta = json.loads((VOCAB_DIR / "clusters.json").read_text())
    words = [w for path in sorted(VOCAB_DIR.glob("words_*.json")) for w in json.loads(path.read_text())["words"]]
    return meta, words


def cluster_hint(lemma: str, words: list[dict]) -> str:
    """Bank words that already list this one as a synonym: it belongs with them."""
    mates = [w for w in words if lemma in w["synonyms"]]
    if not mates:
        return ""
    listed = ", ".join(f'"{w["lemma"]}" (cluster {w["cluster"]})' for w in mates[:5])
    return (f"  These bank words already list \"{lemma}\" as a synonym: {listed}. Use the same\n"
            f"  cluster (or one in the same family) unless the meanings really differ.\n")


async def process(client, usage, sem, lemma: str, rules: dict) -> dict:
    async with sem:
        try:
            entry = await call(client, usage, GENERATE_PROMPT.format(lemma=lemma, **rules), ENTRY_SCHEMA, "medium")
            review = await call(client, usage, VERIFY_PROMPT.format(entry=json.dumps(entry, indent=2)),
                                VERIFY_SCHEMA, "high")
            problems = auto_checks(entry, lemma) + review["problems"]
            revised = False
            if problems or not review["accurate"]:
                entry = await call(
                    client, usage,
                    REVISE_PROMPT.format(lemma=lemma, entry=json.dumps(entry, indent=2),
                                         problems="\n".join(f"- {p}" for p in problems) or "- (marked inaccurate)",
                                         **rules),
                    ENTRY_SCHEMA, "medium",
                )
                review = await call(client, usage, VERIFY_PROMPT.format(entry=json.dumps(entry, indent=2)),
                                    VERIFY_SCHEMA, "high")
                problems = auto_checks(entry, lemma) + review["problems"]
                revised = True
        except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as exc:
            return {"lemma": lemma, "status": "error", "error": str(exc)}
    status = "ok" if review["accurate"] and not auto_checks(entry, lemma) else "needs_review"
    return {"lemma": lemma, "status": status, "revised": revised, "problems": problems, "entry": entry}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lemmas", type=Path, help="text file, one word per line")
    parser.add_argument("-o", "--out", type=Path, default=Path("generated.json"))
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--limit", type=int, help="only the first N words still to do (for a trial run)")
    args = parser.parse_args()

    lemmas = list(dict.fromkeys(l.strip().lower() for l in args.lemmas.read_text().splitlines() if l.strip()))
    meta, words = bank_context()
    existing = {w["lemma"] for w in words}
    done = {r["lemma"]: r for r in json.loads(args.out.read_text())} if args.out.exists() else {}
    done = {k: r for k, r in done.items() if r["status"] != "error"}  # retry errors
    todo = [l for l in lemmas if l not in existing and l not in done][: args.limit]
    print(f"{len(todo)} to generate ({len(done)} already done, "
          f"{sum(l in existing for l in lemmas)} already in the bank)", file=sys.stderr, flush=True)

    shared = {
        "clusters": "\n".join(f"  {k}: {c['label']}" + (f" [{c['family']}]" if c.get("family") else "")
                              for k, c in meta["clusters"].items()),
        "families": "\n".join(f"  {k}: {label}" for k, label in meta["families"].items()),
    }
    key = get_secrets().anthropic_api_key  # else the SDK's usual lookup
    kwargs = {"max_retries": 8}
    client = anthropic.AsyncAnthropic(api_key=key.get_secret_value(), **kwargs) if key else anthropic.AsyncAnthropic(**kwargs)
    sem, usage = asyncio.Semaphore(args.concurrency), Usage()
    results = dict(done)

    def save() -> None:
        ordered = [results[l] for l in lemmas if l in results]
        args.out.write_text(json.dumps(ordered, indent=2))

    tasks = [asyncio.create_task(process(client, usage, sem, l, {**shared, "hint": cluster_hint(l, words)}))
             for l in todo]
    for n, task in enumerate(asyncio.as_completed(tasks), 1):
        r = await task
        results[r["lemma"]] = r
        save()
        if n % 10 == 0 or n == len(tasks):
            print(f"{n}/{len(tasks)} done; {usage.calls} calls, {usage.input} input / {usage.output} output tokens",
                  file=sys.stderr, flush=True)

    save()
    counts = {s: sum(r["status"] == s for r in results.values()) for s in ("ok", "needs_review", "error")}
    print(f"wrote {args.out}: {counts}; this run: {usage.calls} calls, "
          f"{usage.input} input / {usage.output} output tokens", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
