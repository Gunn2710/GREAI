import asyncio

from sqlalchemy import select

from app.items.base import get_item_type
from app.models import Attempt, IssuedItem, Item, UserParams, UserSkill
from app.seed.items import load_items, sync_items, validate_items


def headers(user: str) -> dict:
    return {"X-Dev-User": user}


def right_answer(issued: IssuedItem) -> dict:
    return {"selected": issued.answer["indices"]}


def wrong_answer(issued: IssuedItem) -> dict:
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
            if item.item_type == "tc":
                picked = [built.payload["blanks"][b][i] for b, i in enumerate(built.answer["indices"])]
                assert picked == [opts[0] for opts in item.content["blanks"]]
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
    assert client.get("/api/practice/next?kind=quant", headers=h).status_code == 422
