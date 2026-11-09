import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.items.base import get_item_type
from app.items.vocab import related
from app.models import Card, Confusion, IssuedItem, Word, utcnow
from app.seed.seed import TOP_SOURCE, assign_sets, load_bank, load_groups, sync_bank, validate_bank
from app.services import ai

BANK_META, BANK_WORDS = load_bank()


def headers(user: str) -> dict:
    return {"X-Dev-User": user}


def correct_response(item: IssuedItem) -> dict:
    if item.item_type == "flashcard":
        return {"self_rating": 3}
    if item.item_type in ("meaning", "cloze"):
        return {"selected": item.answer["index"]}
    if item.item_type == "synonyms":
        return {"selected": item.answer["indices"]}
    return {"sentence": "placeholder"}


def test_every_word_builds_every_mode(client, db):
    words = list(db.scalars(select(Word)))
    assert len(words) == len(BANK_WORDS)
    by_lemma = {w.lemma: w for w in words}
    for word in words:
        for name in ("meaning", "cloze", "synonyms"):
            built = get_item_type(name).build(db, "builder", word)
            assert built is not None, (name, word.lemma)
            opts = built.payload["options"]
            assert len(opts) == len(set(opts)), (name, word.lemma, opts)
            if name == "synonyms":
                assert len(opts) == 6
                picked = {opts[i] for i in built.answer["indices"]}
                assert word.lemma in picked
                # Exactly one synonymous pair: no two other options are related.
                others = [by_lemma[o] for o in opts if o in by_lemma and o not in picked]
                for i, a in enumerate(others):
                    for b in others[i + 1:]:
                        assert not related(a, b), (word.lemma, a.lemma, b.lemma)
            else:
                assert len(opts) == 4
                assert built.answer["word_ids"][built.answer["index"]] == word.id


def test_cloze_never_offers_opposites(client, db):
    laud = db.scalar(select(Word).where(Word.lemma == "laud"))
    criticize = {w.lemma for w in db.scalars(select(Word).where(Word.cluster == "criticize"))}
    for _ in range(30):
        built = get_item_type("cloze").build(db, "builder", laud)
        assert not criticize & set(built.payload["options"]), built.payload["options"]


def test_new_word_flow(client, db):
    h = headers("alice")
    res = client.get("/api/study/next", headers=h).json()
    assert res["done"] is False
    assert res["is_new_word"] is True
    item = res["item"]
    assert item["item_type"] == "flashcard"
    assert "back" in item["payload"]
    assert item["payload"]["pronunciation"] and item["payload"]["back"]["pronunciation"]
    assert 2 <= len(item["payload"]["back"]["phrases"]) <= 4
    assert "answer" not in item

    out = client.post(
        f"/api/study/items/{item['id']}/answer",
        json={"response": {"self_rating": 3}, "response_ms": 4200},
        headers=h,
    ).json()
    assert out["correct"] is True
    assert out["rating"] == "good"
    assert out["card"]["tier"] == "learning"

    again = client.post(
        f"/api/study/items/{item['id']}/answer",
        json={"response": {"self_rating": 3}, "response_ms": 4200},
        headers=h,
    )
    assert again.status_code == 409


def test_daily_new_word_limit(client, db):
    h = headers("bob")
    client.put("/api/me/profile", json={"daily_new_words": 3}, headers=h)
    seen = set()
    for _ in range(10):
        res = client.get("/api/study/next", headers=h).json()
        if res["done"]:
            break
        item = db.get(IssuedItem, res["item"]["id"])
        seen.add(item.word_id)
        client.post(
            f"/api/study/items/{item.id}/answer",
            json={"response": correct_response(item), "response_ms": 3000, "confidence": "sure"},
            headers=h,
        )
        db.expire_all()
    # Learning steps are minutes away, so only the 3 new words are served today.
    assert len(seen) == 3
    stats = client.get("/api/stats", headers=h).json()
    assert stats["new_available_today"] == 0
    assert stats["tiers"]["learning"] == 3
    assert stats["reviews_today"] == 3


def _make_review_card(db, user: str, lemma: str, depth: int) -> Card:
    word = db.scalar(select(Word).where(Word.lemma == lemma))
    card = Card(
        user_id=user, word_id=word.id, state=2, stability=5.0, difficulty=5.0,
        due=utcnow() - timedelta(days=1), last_review=utcnow() - timedelta(days=6),
        reps=4, depth=depth, created_at=utcnow() - timedelta(days=10),
    )
    db.add(card)
    db.commit()
    return card


def test_frontier_mode_hint_and_confusion(client, db):
    user = "carol"
    h = headers(user)
    client.put("/api/me/profile", json={"daily_new_words": 0}, headers=h)
    card = _make_review_card(db, user, "enervate", depth=0)

    res = client.get("/api/study/next", headers=h).json()
    item = db.get(IssuedItem, res["item"]["id"])
    assert item.word_id == card.word_id
    assert item.item_type == "meaning"  # depth 0 -> frontier is recognition

    hint = client.post(f"/api/study/items/{item.id}/hint", headers=h).json()
    assert len(hint["eliminate"]) == 2
    assert item.answer["index"] not in hint["eliminate"]

    wrong = next(i for i in range(4) if i != item.answer["index"])
    out = client.post(
        f"/api/study/items/{item.id}/answer",
        json={"response": {"selected": wrong}, "response_ms": 5000, "confidence": "sure"},
        headers=h,
    ).json()
    assert out["correct"] is False
    assert out["rating"] == "again"
    assert out["feedback"]["correct_index"] == item.answer["index"]

    db.expire_all()
    confusion = db.scalar(select(Confusion).where(Confusion.user_id == user))
    assert confusion.target_word_id == card.word_id
    assert confusion.chosen_word_id == item.answer["word_ids"][wrong]
    refreshed = db.get(Card, (user, card.word_id))
    assert refreshed.state == 3  # relearning
    assert refreshed.calibration < 0.5


def test_usage_never_served_without_ai(client, db):
    user = "dave"
    h = headers(user)
    client.put("/api/me/profile", json={"daily_new_words": 0}, headers=h)
    _make_review_card(db, user, "laconic", depth=3)
    types = set()
    for _ in range(15):
        res = client.get("/api/study/next", headers=h).json()
        item = db.get(IssuedItem, res["item"]["id"])
        types.add(item.item_type)
        db.delete(item)  # leave the card due so it gets served again
        db.commit()
    assert "usage" not in types


def test_usage_grading_uses_claude(client, db, monkeypatch):
    async def fake_check(word, sentence):
        return {"correct": True, "score": 0.9, "feedback": "Nice.", "improved_sentence": sentence}

    monkeypatch.setattr(ai.claude, "check_usage", fake_check)
    word = db.scalar(select(Word).where(Word.lemma == "terse"))
    usage = get_item_type("usage")
    item = IssuedItem(id="usage-test", user_id="erin", section="verbal", item_type="usage",
                      word_id=word.id, payload={}, answer={})

    grade = asyncio.run(usage.grade(db, item, {"sentence": "Her terse reply ended the meeting."}))
    assert grade.correct and grade.feedback["ai_feedback"] == "Nice."

    # Sentences that don't contain the word are rejected without calling Claude.
    grade = asyncio.run(usage.grade(db, item, {"sentence": "This sentence has no target."}))
    assert grade.correct is False


def test_users_are_isolated(client):
    a = client.get("/api/stats", headers=headers("alice")).json()
    z = client.get("/api/stats", headers=headers("zed")).json()
    assert a["reviews_today"] >= 1
    assert z["reviews_today"] == 0
    assert z["tiers"]["new"] == len(BANK_WORDS)


def test_word_endpoints(client):
    words = client.get("/api/words?search=laco", headers=headers("alice")).json()
    assert [w["lemma"] for w in words] == ["laconic"]
    detail = client.get(f"/api/words/{words[0]['id']}", headers=headers("alice")).json()
    assert detail["word"]["synonyms"]
    assert detail["word"]["pronunciation"] == "luh-KAH-nik"
    assert detail["word"]["phrases"] == ["laconic reply", "laconic style", "laconic wit"]
    tutor = client.post(
        f"/api/words/{words[0]['id']}/tutor",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers=headers("alice"),
    )
    assert tutor.status_code == 503  # AI disabled in tests


def test_bank_is_valid():
    assert validate_bank(BANK_META, BANK_WORDS) == []
    sources = {w.get("freq_source") for w in BANK_WORDS}
    assert sum(w.get("freq_source") == "magoosh_top20" for w in BANK_WORDS) == 20
    assert sources <= {None, "editorial", "magoosh_top20"}


def test_phrases_must_use_the_word():
    laud = next(w for w in BANK_WORDS if w["lemma"] == "laud")
    extol = next(w for w in BANK_WORDS if w["lemma"] == "extol")
    # Inflections count ("lauded", "extolled"); other words and derivations don't.
    assert any("lauded" in p for p in laud["phrases"]) and any("extolled" in p for p in extol["phrases"])
    for bad in (["praise someone highly", "laud the team"], ["a laudable effort", "laud the team"], ["laud the team"]):
        words = [{**w, "phrases": bad} if w is laud else w for w in BANK_WORDS]
        assert validate_bank(BANK_META, words) == ["laud: needs 2-4 common phrases that each use the word"]


def test_sync_is_idempotent_and_updates(client, db):
    assert sync_bank(db) == {"added": 0, "updated": 0, "total": len(BANK_WORDS)}
    word = db.scalar(select(Word).where(Word.lemma == "laud"))
    word.tier = 3
    db.commit()
    assert sync_bank(db)["updated"] == 1
    db.refresh(word)
    assert word.tier == 1


def test_new_words_start_with_gregmat_group_1(client, db):
    h = headers("frank")
    res = client.get("/api/study/next", headers=h).json()
    item = db.get(IssuedItem, res["item"]["id"])
    assert db.get(Word, item.word_id).lemma == load_groups()[0][0]
    assert res["set"]["number"] == 1 and res["set"]["source"] == "gregmat"


def test_bank_splits_into_sets_most_common_first():
    sets = assign_sets(BANK_WORDS)
    assert set(sets) == {w["lemma"] for w in BANK_WORDS}
    tier = {w["lemma"]: w["tier"] for w in BANK_WORDS}
    members: dict[int, list[str]] = {}
    for lemma, (number, _) in sets.items():
        members.setdefault(number, []).append(lemma)
    assert sorted(members) == list(range(1, len(members) + 1))
    assert all(20 <= len(m) <= 30 for m in members.values())
    # Sets never mix tiers, and tiers only go up through the progression.
    tiers = [{tier[lemma] for lemma in members[n]} for n in sorted(members)]
    assert all(len(t) == 1 for t in tiers)
    assert [t.pop() for t in tiers] == sorted(tier[members[n][0]] for n in members)
    # The most-tested words open the first set.
    top = {w["lemma"] for w in BANK_WORDS if w.get("freq_source") == TOP_SOURCE}
    assert top <= set(members[1])
    # Ranks give one total order that agrees with the set numbers.
    ranked = sorted(sets.values(), key=lambda v: v[1])
    assert [r for _, r in ranked] == list(range(1, len(sets) + 1))
    assert [n for n, _ in ranked] == sorted(n for n, _ in ranked)


def test_sets_follow_the_gregmat_groups():
    groups = load_groups()
    assert len(groups) == 32 and all(len(g) == 30 for g in groups)
    grouped = {lemma for g in groups for lemma in g}
    assert grouped <= {w["lemma"] for w in BANK_WORDS}  # every listed word has an entry
    sets = assign_sets(BANK_WORDS, groups)
    for n, group in enumerate(groups, 1):
        for lemma in group:
            first = next(i for i, g in enumerate(groups, 1) if lemma in g)
            assert sets[lemma][0] == first  # a word listed twice stays in its first group
    # Group order is the study order, and the rest of the bank comes after.
    ranked = [lemma for lemma, _ in sorted(sets.items(), key=lambda kv: kv[1][1])]
    assert ranked[:30] == groups[0]
    rest = [v for lemma, v in sets.items() if lemma not in grouped]
    assert rest and min(n for n, _ in rest) == 33
    assert [n for n, _ in sorted(sets.values(), key=lambda v: v[1])] == sorted(n for n, _ in sets.values())


def test_groups_skip_duplicates_and_missing_words():
    words = [{"lemma": l, "tier": 1, "cluster": "c"} for l in ("ant", "bee", "cat", "dog")]
    sets = assign_sets(words, [["bee", "ant"], ["ant", "yak"], ["zebra"], ["cat"]])
    assert sets == {"bee": (1, 1), "ant": (1, 2), "cat": (2, 3), "dog": (3, 4)}


def test_new_words_come_from_the_current_set(client, db):
    h = headers("grace")
    client.put("/api/me/profile", json={"daily_new_words": 3}, headers=h)
    data = client.get("/api/sets", headers=h).json()
    assert data["current"] == 1
    assert [s["status"] for s in data["sets"][:2]] == ["current", "locked"]
    assert data["sets"][0]["started"] == 0

    res = client.get("/api/study/next", headers=h).json()
    assert res["set"]["number"] == 1 and res["set"]["total"] == len(data["sets"])
    item = db.get(IssuedItem, res["item"]["id"])
    first = db.scalar(select(Word).order_by(Word.set_rank).limit(1))
    assert item.word_id == first.id

    # Placing the rest of set 1 moves the progression on to set 2.
    for word in db.scalars(select(Word).where(Word.set_no == 1, Word.id != first.id)):
        db.add(Card(user_id="grace", word_id=word.id, origin="placement", reps=1, state=2,
                    stability=30.0, difficulty=4.0, depth=3, last_review=utcnow(),
                    due=utcnow() + timedelta(days=20), created_at=utcnow() - timedelta(days=2)))
    db.commit()
    data = client.get("/api/sets", headers=h).json()
    assert data["current"] == 2
    assert data["sets"][0]["status"] in ("reviewing", "done")
    assert client.get("/api/stats", headers=h).json()["sets"]["current"]["number"] == 2


def test_mode_chain_honours_the_chosen_format():
    from app.services.study import mode_chain

    assert mode_chain("usage") == ["usage", "synonyms", "cloze", "meaning", "flashcard"]
    assert mode_chain("cloze", "flashcard") == ["flashcard"]
    # Multiple choice only: nearest MCQ mode first, flashcard as the last resort.
    assert mode_chain("usage", "mcq") == ["synonyms", "cloze", "meaning", "flashcard"]
    assert mode_chain("flashcard", "mcq") == ["meaning", "cloze", "synonyms", "flashcard"]
    assert mode_chain("cloze", "mcq") == ["cloze", "meaning", "synonyms", "flashcard"]


@pytest.mark.parametrize("fmt, allowed", [
    ("flashcard", {"flashcard"}),
    ("mcq", {"meaning", "cloze", "synonyms"}),
])
def test_study_format_filter(client, fmt, allowed):
    h = headers(f"format-{fmt}")
    client.put("/api/me/profile", json={"daily_new_words": 6}, headers=h)
    for _ in range(6):
        res = client.get(f"/api/study/next?format={fmt}", headers=h).json()
        assert res["item"]["item_type"] in allowed
        response = {"self_rating": 3} if fmt == "flashcard" else {"selected": 0}
        client.post(f"/api/study/items/{res['item']['id']}/answer",
                    json={"response": response, "response_ms": 4000}, headers=h)


def test_unknown_study_format_is_rejected(client):
    assert client.get("/api/study/next?format=essay", headers=headers("x")).status_code == 422


def _start_new_words(client, h, n):
    """Answer flashcards until n new words are started (or the day is done)."""
    for _ in range(n * 3):
        res = client.get("/api/study/next?format=flashcard", headers=h).json()
        if res["done"]:
            return res
        client.post(f"/api/study/items/{res['item']['id']}/answer",
                    json={"response": {"self_rating": 4}, "response_ms": 3000}, headers=h)
    return client.get("/api/study/next", headers=h).json()


def test_study_more_raises_todays_limit(client, db):
    from app.services.study import new_words_started_today

    h = headers("eager")
    client.put("/api/me/profile", json={"daily_new_words": 2}, headers=h)
    res = _start_new_words(client, h, 2)
    assert res["done"] and res["new_word_limit"] == 2 and res["unseen_words"] > 0
    assert new_words_started_today(db, "eager") == 2

    more = client.post("/api/study/more", json={"words": 3}, headers=h).json()
    assert more == {"extra_today": 3, "new_word_limit": 5}
    assert client.get("/api/stats", headers=h).json()["new_available_today"] == 3
    res = _start_new_words(client, h, 3)
    assert res["done"] and res["new_word_limit"] == 5
    db.expire_all()
    assert new_words_started_today(db, "eager") == 5
    # The setting itself is unchanged.
    assert client.get("/api/me/profile", headers=h).json()["daily_new_words"] == 2


def test_study_more_is_for_today_only(client, db):
    from datetime import date

    from app.models import Profile

    h = headers("yesterday")
    client.post("/api/study/more", json={"words": 5}, headers=h)
    profile = db.get(Profile, "yesterday")
    db.refresh(profile)
    profile.extra_new_words_on = date(2020, 1, 1)
    db.commit()
    assert client.post("/api/study/more", json={"words": 2}, headers=h).json()["extra_today"] == 2
    assert client.post("/api/study/more", json={"words": 0}, headers=h).status_code == 422


class FakeClaude:
    """Stands in for the Messages API: replays canned responses, records calls."""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    async def __call__(self, **params):
        self.calls.append({**params, "messages": list(params["messages"])})
        return self.responses.pop(0)


def _text(text):
    from types import SimpleNamespace as NS
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)])


def _tool(name, **args):
    from types import SimpleNamespace as NS
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", id="tu_1", name=name, input=args)])


def _mcq_item(client, h):
    res = client.get("/api/study/next?format=mcq", headers=h).json()
    return res["item"]


def test_study_chat_coaches_without_answering_first(client, db, monkeypatch):
    h = headers("chatty")
    item = _mcq_item(client, h)
    word = db.get(Word, db.get(IssuedItem, item["id"]).word_id)
    other = db.scalar(select(Word).where(Word.id != word.id).limit(1))
    fake = FakeClaude(_tool("look_up_word", word=other.lemma.upper()), _text("Think about the root."))
    monkeypatch.setattr(ai.claude, "_create", fake)

    res = client.post(f"/api/study/items/{item['id']}/chat", headers=h,
                      json={"messages": [{"role": "user", "content": "What's the answer?"}]}).json()
    assert res == {"reply": "Think about the root.", "counted_as_hint": True}
    system = fake.calls[0]["system"]
    assert "HAS NOT ANSWERED YET" in system and "Correct answer:" in system and word.lemma in system
    # The tool ran against the word bank and its result went back to Claude.
    tool_result = fake.calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and other.definition in tool_result["content"]
    db.expire_all()
    assert db.get(IssuedItem, item["id"]).hint_used


def test_study_chat_explains_freely_after_answering(client, db, monkeypatch):
    h = headers("after")
    item = _mcq_item(client, h)
    client.post(f"/api/study/items/{item['id']}/answer", headers=h,
                json={"response": {"selected": 0}, "response_ms": 4000})
    fake = FakeClaude(_tool("student_history"), _text("Here's why."))
    monkeypatch.setattr(ai.claude, "_create", fake)

    res = client.post(f"/api/study/items/{item['id']}/chat", headers=h,
                      json={"messages": [{"role": "user", "content": "Why?"}]}).json()
    assert res == {"reply": "Here's why.", "counted_as_hint": False}
    system = fake.calls[0]["system"]
    assert "has answered" in system and "Chose A" in system
    history = fake.calls[1]["messages"][-1]["content"][0]["content"]
    assert '"recent_attempts": [{' in history


def test_study_chat_is_private(client, monkeypatch):
    item = _mcq_item(client, headers("owner"))
    monkeypatch.setattr(ai.claude, "_create", FakeClaude(_text("hi")))
    res = client.post(f"/api/study/items/{item['id']}/chat", headers=headers("someone-else"),
                      json={"messages": [{"role": "user", "content": "hi"}]})
    assert res.status_code == 404


def test_both_tutors_carry_the_topic_rules(client, db, monkeypatch):
    h = headers("scoped")
    item = _mcq_item(client, h)
    fake = FakeClaude(_text("ok"), _text("ok"))
    monkeypatch.setattr(ai.claude, "_create", fake)
    monkeypatch.setattr(ai.claude.settings, "ai_enabled", True)
    msgs = {"messages": [{"role": "user", "content": "what is 5 times 5"}]}
    client.post(f"/api/study/items/{item['id']}/chat", headers=h, json=msgs)
    word_id = db.get(IssuedItem, item["id"]).word_id
    client.post(f"/api/words/{word_id}/tutor", headers=h, json=msgs)
    assert len(fake.calls) == 2
    assert all(ai.TUTOR_SCOPE in call["system"] for call in fake.calls)
