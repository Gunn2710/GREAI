import asyncio

from sqlalchemy import select

from app.items.base import get_item_type
from app.models import Attempt, IssuedItem, Item, UserParams, UserSkill
from app.seed.items import load_items, parse_number, sync_items, validate_items


def headers(user: str) -> dict:
    return {"X-Dev-User": user}


def right_answer(issued: IssuedItem) -> dict:
    if issued.item_type == "qne":
        return {"value": issued.answer["value"]}
    return {"selected": issued.answer["indices"]}


def wrong_answer(issued: IssuedItem) -> dict:
    if issued.item_type == "qne":
        return {"value": str(parse_number(issued.answer["value"]) + 1)}
    if issued.item_type in ("rc", "qc", "qmc"):
        n = len(issued.payload["options"])
        return {"selected": [next(i for i in range(n) if [i] != issued.answer["indices"])]}
    if issued.item_type == "se":
        a, b = issued.answer["indices"]
        other = next(i for i in range(6) if i not in (a, b))
        return {"selected": [a, other]}  # one right, one wrong: still no credit
    first, *rest = issued.answer["indices"]
    return {"selected": [(first + 1) % len(issued.payload["blanks"][0]), *rest]}


def test_bank_is_valid_and_synced(client, db):
    banks = load_items()
    assert validate_items(banks) == []
    assert db.scalar(select(Item).where(Item.slug == "tc-t05")).item_type == "tc"
    total = sum(len(v) for v in banks.values())
    assert sync_items(db) == {"added": 0, "updated": 0, "total": total}


def test_shuffled_answers_match_authored_answers(client, db):
    for item in db.scalars(select(Item)):
        for _ in range(5):
            built = get_item_type(item.item_type).build(db, "u", item)
            c = item.content
            if item.item_type == "tc":
                picked = [built.payload["blanks"][b][i] for b, i in enumerate(built.answer["indices"])]
                assert picked == [opts[0] for opts in c["blanks"]]
            elif item.item_type == "rc":
                picked = {built.payload["options"][i] for i in built.answer["indices"]}
                assert picked == set(c["options"][: 1 if c["select"] == "one" else c["correct"]])
                assert built.payload["passage"] == c["passage"]
            elif item.item_type == "qc":
                assert built.answer["indices"] == ["ABCD".index(c["answer"])]
            elif item.item_type == "qmc":
                assert built.payload["options"] == c["options"]  # quant options keep their order
                assert built.answer["indices"] == sorted(c["answer"])
            elif item.item_type == "qne":
                assert built.answer["value"] == c["answer"] and "answer" not in built.payload
            else:
                picked = {built.payload["options"][i] for i in built.answer["indices"]}
                assert picked == set(item.content["options"][:2])


def test_grading_is_all_or_nothing(client, db):
    tc = get_item_type("tc")
    item = db.scalar(select(Item).where(Item.slug == "tc-t01"))
    built = tc.build(db, "u", item)
    issued = IssuedItem(id="g1", user_id="u", section="verbal", item_type="tc",
                        bank_item_id=item.id, payload=built.payload, answer=built.answer)
    assert asyncio.run(tc.grade(db, issued, right_answer(issued))).correct
    assert not asyncio.run(tc.grade(db, issued, wrong_answer(issued))).correct
    grade = asyncio.run(tc.grade(db, issued, right_answer(issued)))
    assert "{" not in grade.feedback["filled_text"]
    assert "concision" in grade.feedback["filled_text"]

    se = get_item_type("se")
    item = db.scalar(select(Item).where(Item.slug == "se-01"))
    built = se.build(db, "u", item)
    issued = IssuedItem(id="g2", user_id="u", section="verbal", item_type="se",
                        bank_item_id=item.id, payload=built.payload, answer=built.answer)
    a, b = issued.answer["indices"]
    assert asyncio.run(se.grade(db, issued, {"selected": [b, a]})).correct  # order doesn't matter
    assert not asyncio.run(se.grade(db, issued, {"selected": [a]})).correct
    assert not asyncio.run(se.grade(db, issued, wrong_answer(issued))).correct
    words = {w["lemma"] for w in asyncio.run(se.grade(db, issued, {"selected": [a, b]})).feedback["words"]}
    assert {"laconic", "taciturn", "garrulous", "loquacious"} <= words


def answer_n(client, db, user, kind, n, correct):
    ratings, seen = [], []
    for _ in range(n):
        item = client.get(f"/api/practice/next?kind={kind}", headers=headers(user)).json()["item"]
        issued = db.get(IssuedItem, item["id"])
        seen.append(issued.bank_item_id)
        body = {"response": right_answer(issued) if correct else wrong_answer(issued), "response_ms": 30000}
        res = client.post(f"/api/practice/items/{item['id']}/answer", json=body, headers=headers(user))
        assert res.status_code == 200, res.text
        out = res.json()
        assert out["correct"] is correct
        assert out["feedback"]["explanation"]
        ratings.append(out["rating_after"])
        db.expire_all()
    return ratings, seen


def test_ratings_move_and_questions_dont_repeat(client, db):
    up, seen_up = answer_n(client, db, "pr-good", "tc", 8, correct=True)
    down, _ = answer_n(client, db, "pr-bad", "se", 6, correct=False)
    assert up == sorted(up) and up[-1] > 0
    assert down == sorted(down, reverse=True) and down[-1] < 0
    assert len(set(seen_up)) == len(seen_up)

    summary = client.get("/api/practice/summary", headers=headers("pr-good")).json()
    assert summary["tc"]["attempts"] == 8 and summary["tc"]["accuracy"] == 1.0
    assert summary["se"]["attempts"] == 0 and summary["se"]["rating"] is None

    # Practice answers don't count as vocabulary reviews on the dashboard.
    stats = client.get("/api/stats", headers=headers("pr-good")).json()
    assert stats["reviews_today"] == 0
    assert db.scalar(select(Attempt).where(Attempt.user_id == "pr-good")).item_type == "tc"


def test_unanswered_questions_are_not_hidden(client, db):
    """Answer one question, fetch and abandon the other: the abandoned one must
    count as unseen and come next (not the answered one)."""
    h = headers("pr-abandon")
    keep = {"se-01", "se-02"}
    others = list(db.scalars(select(Item).where(Item.item_type == "se", Item.slug.not_in(keep))))
    for it in others:
        it.status = "inactive"
    db.commit()
    try:
        item = client.get("/api/practice/next?kind=se", headers=h).json()["item"]
        issued = db.get(IssuedItem, item["id"])
        answered = issued.bank_item_id
        client.post(f"/api/practice/items/{item['id']}/answer",
                    json={"response": right_answer(issued), "response_ms": 1000}, headers=h)
        abandoned = db.get(IssuedItem, client.get("/api/practice/next?kind=se", headers=h).json()["item"]["id"])
        assert abandoned.bank_item_id != answered
        again = db.get(IssuedItem, client.get("/api/practice/next?kind=se", headers=h).json()["item"]["id"])
        assert again.bank_item_id == abandoned.bank_item_id
    finally:
        for it in others:
            it.status = "active"
        db.commit()


def test_rating_starts_from_placement_level(client, db):
    db.add(UserParams(user_id="pr-placed", speed_baselines={}, vocab_level=1.2))
    db.commit()
    client.get("/api/practice/next?kind=se", headers=headers("pr-placed"))
    assert db.get(UserSkill, ("pr-placed", "verbal.se")).rating == 1.2


def test_hint_and_errors(client, db):
    h = headers("pr-hint")
    item = client.get("/api/practice/next?kind=tc", headers=h).json()["item"]
    assert client.post(f"/api/practice/items/{item['id']}/hint", headers=h).json()["clue"]
    issued = db.get(IssuedItem, item["id"])
    body = {"response": right_answer(issued), "response_ms": 1000}
    assert client.post(f"/api/practice/items/{item['id']}/answer", json=body, headers=headers("intruder")).status_code == 404
    assert client.post(f"/api/practice/items/{item['id']}/answer", json=body, headers=h).status_code == 200
    assert client.post(f"/api/practice/items/{item['id']}/answer", json=body, headers=h).status_code == 409
    assert client.get("/api/practice/next?kind=writing", headers=h).status_code == 422


def test_new_sections_are_synced(client, db):
    kinds = {i.item_type: i.section for i in db.scalars(select(Item))}
    assert kinds == {"tc": "verbal", "se": "verbal", "rc": "verbal",
                     "qc": "quant", "qmc": "quant", "qne": "quant"}
    rc = db.scalar(select(Item).where(Item.slug == "rc-p01-q2"))
    assert rc.content["passage_slug"] == "rc-p01" and rc.content["order"] == 2 and rc.content["of"] == 5


def test_every_new_kind_grades_right_and_wrong(client, db):
    for kind in ("rc", "qc", "qmc", "qne"):
        ratings, _ = answer_n(client, db, f"pr-{kind}", kind, 3, correct=True)
        assert ratings == sorted(ratings)
        answer_n(client, db, f"pr-{kind}-bad", kind, 2, correct=False)
    summary = client.get("/api/practice/summary", headers=headers("pr-qc")).json()
    assert summary["qc"]["attempts"] == 3 and summary["qc"]["section"] == "quant"
    attempt = db.scalar(select(Attempt).where(Attempt.user_id == "pr-qc"))
    assert attempt.section == "quant"


def test_mixed_quant_serves_only_quant(client, db):
    h = headers("pr-quant-mix")
    for _ in range(8):
        item = client.get("/api/practice/next?kind=quant", headers=h).json()["item"]
        assert item["item_type"] in ("qc", "qmc", "qne")
        issued = db.get(IssuedItem, item["id"])
        assert issued.section == "quant"


def test_reading_passages_are_served_in_order(client, db):
    h = headers("pr-reader")
    served = []
    for _ in range(12):
        item = client.get("/api/practice/next?kind=rc", headers=h).json()["item"]
        issued = db.get(IssuedItem, item["id"])
        served.append((item["payload"]["passage"], item["payload"]["order"], item["payload"]["of"]))
        client.post(f"/api/practice/items/{item['id']}/answer",
                    json={"response": right_answer(issued), "response_ms": 1000}, headers=h)
        db.expire_all()
    # Each passage appears as one unbroken run of questions 1..n.
    runs, i = [], 0
    while i < len(served):
        passage, _, n = served[i]
        assert [o for _, o, _ in served[i:i + n]] == list(range(1, n + 1))
        assert {p for p, _, _ in served[i:i + n]} == {passage}
        runs.append(passage)
        i += n
    assert len(runs) == len(set(runs)) == 3


def test_numeric_entry_accepts_equivalent_values(client, db):
    qne = get_item_type("qne")
    for slug, good, bad in [("qne-04", ["1/9", "4/36", " 2/18 "], ["0.111", "1/8", "", "abc", "1/0"]),
                            ("qne-01", ["10.5", "21/2", "10.50"], ["10", "105"]),
                            ("qne-05", ["108", "108.0", "1,080/10"], ["-108"])]:
        item = db.scalar(select(Item).where(Item.slug == slug))
        built = qne.build(db, "u", item)
        issued = IssuedItem(id=f"ne-{slug}", user_id="u", section="quant", item_type="qne",
                            bank_item_id=item.id, payload=built.payload, answer=built.answer)
        for v in good:
            assert asyncio.run(qne.grade(db, issued, {"value": v})).correct, (slug, v)
        for v in bad:
            assert not asyncio.run(qne.grade(db, issued, {"value": v})).correct, (slug, v)
    assert asyncio.run(qne.grade(db, issued, {})).feedback["correct_answer"] == "108"


def test_multi_answer_needs_every_right_choice(client, db):
    qmc = get_item_type("qmc")
    item = db.scalar(select(Item).where(Item.slug == "qmc-06"))
    built = qmc.build(db, "u", item)
    issued = IssuedItem(id="mc6", user_id="u", section="quant", item_type="qmc",
                        bank_item_id=item.id, payload=built.payload, answer=built.answer)
    assert asyncio.run(qmc.grade(db, issued, {"selected": [3, 0, 1]})).correct
    assert not asyncio.run(qmc.grade(db, issued, {"selected": [0, 1]})).correct
    assert not asyncio.run(qmc.grade(db, issued, {"selected": [0, 1, 2, 3]})).correct


def test_quant_rating_ignores_vocab_level(client, db):
    db.add(UserParams(user_id="pr-placed-q", speed_baselines={}, vocab_level=1.2))
    db.commit()
    client.get("/api/practice/next?kind=qc", headers=headers("pr-placed-q"))
    assert db.get(UserSkill, ("pr-placed-q", "quant.qc")).rating == 0.0


def test_validation_catches_bad_new_items():
    good = load_items()
    bad = {
        "rc": [{**good["rc"][0], "slug": "x1", "options": good["rc"][0]["options"][:4]},
               {**good["rc"][3], "slug": "x2", "correct": 0}],
        "qc": [{**good["qc"][0], "slug": "x3", "answer": "E"}],
        "qmc": [{**good["qmc"][0], "slug": "x4", "answer": [7]},
                {**good["qmc"][3], "slug": "x5", "table": {"columns": ["a"], "rows": [["1", "2"]]}}],
        "qne": [{**good["qne"][0], "slug": "x6", "answer": "ten"},
                {**good["qne"][3], "slug": "x7", "answer": "0.25"},
                {**good["qne"][1], "slug": "x8", "topic": "calculus"}],
    }
    problems = " | ".join(validate_items(bad))
    for slug in ("x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"):
        assert f"{slug}:" in problems, slug


def test_coach_sees_the_practice_question(client, db, monkeypatch):
    from app.services import ai
    from tests.test_api import FakeClaude, _text

    h = headers("pr-coach")
    for kind in ("tc", "rc", "qc", "qne"):
        item = client.get(f"/api/practice/next?kind={kind}", headers=h).json()["item"]
        issued = db.get(IssuedItem, item["id"])
        fake = FakeClaude(_text("Think about it."), _text("Here's why."))
        monkeypatch.setattr(ai.claude, "_create", fake)
        ask = {"messages": [{"role": "user", "content": "Give me a hint"}], "practice_item_id": item["id"]}

        res = client.post("/api/coach/chat", headers=h, json=ask).json()
        assert res["counted_as_hint"] is True
        before = fake.calls[0]["system"]
        assert "on the Practice page" in before and "HAS NOT ANSWERED YET" in before
        assert "Correct answer:" in before and issued.answer["explanation"] in before
        if kind == "rc":
            assert issued.payload["passage"][:40] in before
        db.expire_all()
        assert db.get(IssuedItem, item["id"]).hint_used  # a hinted answer moves the rating less

        client.post(f"/api/practice/items/{item['id']}/answer", headers=h,
                    json={"response": wrong_answer(issued), "response_ms": 5000})
        res = client.post("/api/coach/chat", headers=h, json=ask).json()
        assert res["counted_as_hint"] is False
        after = fake.calls[1]["system"]
        assert "has answered" in after and "(incorrect)" in after


def test_coach_only_opens_your_own_practice_questions(client, monkeypatch):
    from app.services import ai
    from tests.test_api import FakeClaude, _text

    monkeypatch.setattr(ai.claude, "_create", FakeClaude(_text("hi")))
    item = client.get("/api/practice/next?kind=qc", headers=headers("pr-owner")).json()["item"]
    ask = {"messages": [{"role": "user", "content": "hi"}], "practice_item_id": item["id"]}
    assert client.post("/api/coach/chat", headers=headers("pr-other"), json=ask).status_code == 404
    vocab = client.get("/api/study/next?format=mcq", headers=headers("pr-owner")).json()["item"]
    ask["practice_item_id"] = vocab["id"]  # a Vocab question isn't a Practice question
    assert client.post("/api/coach/chat", headers=headers("pr-owner"), json=ask).status_code == 404
