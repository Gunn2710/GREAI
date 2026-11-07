"""Offline content pipeline: generate word entries with Claude, then verify them.

    python scripts/generate_words.py lemmas.txt -o generated.json

Each lemma gets two independent calls:
  1. generate  - a full entry (definition, nuance, examples, synonyms, ...)
  2. verify    - a separate review that checks accuracy and flags problems
Entries pass automatic checks (every example contains the exact lemma, which
cloze items need) before review. Review `generated.json`, then copy accepted
entries into a new app/seed/vocab/words_*.json file; the server validates and
syncs it on the next start.
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
from app.seed.seed import valid_pronunciation  # noqa: E402

MODEL = "claude-opus-5-5"
FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "lemma": {"type": "string"},
        "pos": {"type": "string", "enum": ["noun", "verb", "adjective", "adverb"]},
        "pronunciation": {"type": "string"},
        "definition": {"type": "string"},
        "nuance": {"type": "string"},
        "examples": {"type": "array", "items": {"type": "string"}},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "antonyms": {"type": "array", "items": {"type": "string"}},
        "confusables": {"type": "array", "items": {"type": "string"}},
        "cluster": {"type": "string"},
        "tier": {"type": "integer", "enum": [1, 2, 3]},
    },
    "required": ["lemma", "pos", "pronunciation", "definition", "nuance", "examples", "synonyms",
                 "antonyms", "confusables", "cluster", "tier"],
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

GENERATE_PROMPT = """Write a GRE vocabulary entry for the word "{lemma}".

Requirements:
- pronunciation: American English respelling, hyphenated lowercase syllables
  with the stressed syllable in CAPITALS, e.g. "luh-KAH-nik"; join accepted
  variants with " or ". Use: ah (hot), aw (law), uh (about), ih (sit),
  ee (see), ay (day), y/eye (by), oo (food), yoo (use), oh (go).
- definition: the sense most tested on the GRE, in plain words, lowercase, no trailing period.
- nuance: one sentence on connotation or how it differs from near-synonyms.
- examples: 3 natural sentences in a GRE register. Each must contain the exact
  form "{lemma}" (not an inflection) and make its meaning clear from context.
- synonyms / antonyms: 2-3 single words or short phrases each.
- confusables: words students mix it up with because they look or sound alike
  (empty if none). Never list synonyms here.
- cluster: one lowercase key for its meaning group. Prefer one of: {clusters}.
- tier: 1 = very common on the GRE, 2 = common, 3 = rare."""

VERIFY_PROMPT = """You are checking a GRE vocabulary entry written by someone else.
Flag anything a careful lexicographer would object to: a wrong or misleading
definition, an example that misuses the word, a "synonym" that is not one, or
a "confusable" that is actually related in meaning.

<entry>
{entry}
</entry>"""


def text_of(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


async def call(client, prompt: str, schema: dict, effort: str) -> dict:
    response = await client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        **FALLBACK,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("refused")
    return json.loads(text_of(response))


def auto_checks(entry: dict, lemma: str) -> list[str]:
    problems = []
    if entry["lemma"].lower() != lemma.lower():
        problems.append(f"lemma changed to {entry['lemma']!r}")
    pattern = re.compile(rf"\b{re.escape(lemma)}\b", re.IGNORECASE)
    missing = [s for s in entry["examples"] if not pattern.search(s)]
    if missing:
        problems.append(f"{len(missing)} example(s) lack the exact lemma")
    if not valid_pronunciation(entry.get("pronunciation")):
        problems.append("pronunciation is not a stress-marked respelling")
    if set(entry["confusables"]) & set(entry["synonyms"]):
        problems.append("a confusable is also listed as a synonym")
    return problems


async def process(client, sem, lemma: str, clusters: list[str]) -> dict:
    async with sem:
        try:
            entry = await call(
                client, GENERATE_PROMPT.format(lemma=lemma, clusters=", ".join(clusters)),
                ENTRY_SCHEMA, effort="medium",
            )
            review = await call(
                client, VERIFY_PROMPT.format(entry=json.dumps(entry, indent=2)),
                VERIFY_SCHEMA, effort="high",
            )
        except (anthropic.APIError, RuntimeError, json.JSONDecodeError) as exc:
            return {"lemma": lemma, "status": "error", "error": str(exc)}
    problems = auto_checks(entry, lemma) + review["problems"]
    status = "ok" if review["accurate"] and not problems else "needs_review"
    return {"lemma": lemma, "status": status, "problems": problems, "entry": entry}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lemmas", type=Path, help="text file, one word per line")
    parser.add_argument("-o", "--out", type=Path, default=Path("generated.json"))
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()

    lemmas = [l.strip().lower() for l in args.lemmas.read_text().splitlines() if l.strip()]
    vocab_dir = Path(__file__).parents[1] / "app/seed/vocab"
    clusters = list(json.loads((vocab_dir / "clusters.json").read_text())["clusters"])
    existing = {
        w["lemma"]
        for path in vocab_dir.glob("words_*.json")
        for w in json.loads(path.read_text())["words"]
    }
    todo = [l for l in lemmas if l not in existing]
    print(f"{len(todo)} new words ({len(lemmas) - len(todo)} already in the bank)", file=sys.stderr)

    key = get_secrets().anthropic_api_key  # else the SDK's usual lookup
    client = anthropic.AsyncAnthropic(api_key=key.get_secret_value()) if key else anthropic.AsyncAnthropic()
    sem = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*(process(client, sem, l, clusters) for l in todo))

    args.out.write_text(json.dumps(results, indent=2))
    counts = {s: sum(r["status"] == s for r in results) for s in ("ok", "needs_review", "error")}
    print(f"wrote {args.out}: {counts}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
