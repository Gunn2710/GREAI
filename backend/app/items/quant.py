"""GRE Quantitative item types served from the stored question bank (`items` table).

    qc   Quantitative Comparison: compare Quantity A with Quantity B; four
         fixed choices (A greater, B greater, equal, cannot be determined).
    qmc  Multiple choice: pick one of 5 options, or select every right one.
    qne  Numeric entry: type the value; any equivalent number or fraction counts.

Quant options keep their authored order (numbers are listed in order, as on the
GRE), so answers are stored explicitly instead of "first option is correct".
"""
from app.items.base import BuiltItem, Grade, ItemType, register
from app.models import Item
from app.seed.items import QC_ANSWERS, parse_number

QC_OPTIONS = [
    "Quantity A is greater.",
    "Quantity B is greater.",
    "The two quantities are equal.",
    "The relationship cannot be determined from the information given.",
]


def _common(item: Item) -> dict:
    c = item.content
    return {"topic": c["topic"], "table": c.get("table"), "difficulty": item.difficulty_label}


def _answer(item: Item, **extra) -> dict:
    return {"clue": item.content["clue"], "explanation": item.content["explanation"], **extra}


def _grade_choice(item, response) -> Grade:
    selected = response.get("selected")
    answer = item.answer["indices"]
    ok = isinstance(selected, list) and sorted(selected) == answer
    return Grade(correct=ok, score=1.0 if ok else 0.0,
                 feedback={"correct_indices": answer, "explanation": item.answer["explanation"]})


class QuantComparison(ItemType):
    name, section, hint_available = "qc", "quant", True

    def build(self, db, user_id, item: Item) -> BuiltItem:
        c = item.content
        return BuiltItem(
            payload={"info": c.get("info"), "quantity_a": c["quantity_a"], "quantity_b": c["quantity_b"],
                     "options": QC_OPTIONS, **_common(item)},
            answer=_answer(item, indices=[QC_ANSWERS.index(c["answer"])]),
        )

    async def grade(self, db, item, response) -> Grade:
        return _grade_choice(item, response)

    def hint(self, item):
        return {"clue": item.answer["clue"]}


class QuantMultipleChoice(ItemType):
    name, section, hint_available = "qmc", "quant", True

    def build(self, db, user_id, item: Item) -> BuiltItem:
        c = item.content
        return BuiltItem(
            payload={"text": c["text"], "options": c["options"], "select": c["select"], **_common(item)},
            answer=_answer(item, indices=sorted(c["answer"])),
        )

    async def grade(self, db, item, response) -> Grade:
        return _grade_choice(item, response)

    def hint(self, item):
        return {"clue": item.answer["clue"]}


class QuantNumericEntry(ItemType):
    name, section, hint_available = "qne", "quant", True

    def build(self, db, user_id, item: Item) -> BuiltItem:
        c = item.content
        return BuiltItem(
            payload={"text": c["text"], "unit": c.get("unit"), "fraction": bool(c.get("fraction")),
                     **_common(item)},
            answer=_answer(item, value=c["answer"]),
        )

    async def grade(self, db, item, response) -> Grade:
        given = parse_number(response.get("value", ""))
        ok = given is not None and given == parse_number(item.answer["value"])
        return Grade(correct=ok, score=1.0 if ok else 0.0,
                     feedback={"correct_answer": item.answer["value"], "explanation": item.answer["explanation"]})

    def hint(self, item):
        return {"clue": item.answer["clue"]}


register(QuantComparison())
register(QuantMultipleChoice())
register(QuantNumericEntry())
