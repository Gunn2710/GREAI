from sqlalchemy import select

from app.models import Card, IssuedItem, UserParams, Word
from app.services import placement
from app.services.study import new_words_started_today


def headers(user: str) -> dict:
    return {"X-Dev-User": user}


def run_placement(client, db, user: str, knows) -> dict:
    """Take a whole placement check; `knows(word)` decides each answer
    (True = right, False = wrong, None = "I don't know")."""
    res = client.post("/api/placement/start", headers=headers(user)).json()
    run_id = res["run_id"]
    for _ in range(placement.QUESTIONS + 1):
        if res["done"]:
            return res["result"]
        item = db.get(IssuedItem, res["item"]["id"])
        verdict = knows(db.get(Word, item.word_id))
        if verdict is None:
            selected = None
        elif verdict:
            selected = item.answer["index"]
        else:
            selected = (item.answer["index"] + 1) % 4
        res = client.post(
            f"/api/placement/{run_id}/answer",
            json={"item_id": item.id, "selected": selected, "response_ms": 3000},
            headers=headers(user),
        )
        assert res.status_code == 200, res.text
        res = res.json()
        db.expire_all()
    raise AssertionError("placement never finished")


def test_strong_and_weak_users(client, db):
    strong = run_placement(client, db, "pl-strong", lambda w: w.tier <= 2)
    weak = run_placement(client, db, "pl-weak", lambda w: None)

    for result in (strong, weak):
        assert result["answered"] == placement.QUESTIONS
    assert strong["theta"] > weak["theta"]
    assert weak["correct"] == 0
    assert weak["level"] == "Building"
    assert strong["known_share"]["1"] > weak["known_share"]["1"]

    # Only correct answers become cards, and they don't use the new-word allowance.
    cards = list(db.scalars(select(Card).where(Card.user_id == "pl-strong")))
    assert len(cards) == strong["correct"] == strong["fast_tracked"]
    assert all(c.origin == "placement" and c.state == 2 and c.depth == 1 for c in cards)
    assert new_words_started_today(db, "pl-strong") == 0
    assert abs(db.get(UserParams, "pl-strong").vocab_level - strong["theta"]) < 0.01

    latest = client.get("/api/placement/latest", headers=headers("pl-strong")).json()["result"]
    assert latest["run_id"] == strong["run_id"]
    assert client.get("/api/placement/latest", headers=headers("nobody")).json()["result"] is None


def test_answers_teach_word_difficulty(client, db):
    before = {w.id: w.global_difficulty for w in db.scalars(select(Word))}
    run_placement(client, db, "pl-difficulty", lambda w: False)
    db.expire_all()
    harder = [w for w in db.scalars(select(Word)) if w.global_difficulty > before[w.id]]
    assert harder, "missed words should look harder afterwards"


def test_fast_track_after_placement(client, db):
    user = "pl-fast"
    client.put("/api/me/profile", json={"daily_new_words": 2}, headers=headers(user))
    db.add(UserParams(user_id=user, speed_baselines={}, vocab_level=3.0))
    db.commit()

    res = client.get("/api/study/next", headers=headers(user)).json()
    assert res["likely_known"] is True
    assert res["is_new_word"] is False
    assert res["item"]["item_type"] != "flashcard"
    card = db.scalar(select(Card).where(Card.user_id == user))
    assert card.origin == "fast_track"
    assert new_words_started_today(db, user) == 0


def test_no_fast_track_without_placement(client, db):
    res = client.get("/api/study/next", headers=headers("pl-none")).json()
    assert res["likely_known"] is False
    assert res["item"]["item_type"] == "flashcard"


def test_placement_errors(client, db):
    h = headers("pl-errors")
    res = client.post("/api/placement/start", headers=h).json()
    item_id = res["item"]["id"]
    body = {"item_id": item_id, "selected": 0, "response_ms": 1000}
    assert client.post(f"/api/placement/{res['run_id']}/answer", json=body, headers=h).status_code == 200
    assert client.post(f"/api/placement/{res['run_id']}/answer", json=body, headers=h).status_code == 409
    assert client.post("/api/placement/nope/answer", json=body, headers=h).status_code == 404
    other = client.post(f"/api/placement/{res['run_id']}/answer", json=body, headers=headers("intruder"))
    assert other.status_code == 404
