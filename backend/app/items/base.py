"""Item-type registry.

Every question format (vocab modes now; text completion, quant and essays
later) is an ItemType registered here. The study engine only talks to this
interface, so adding a section means registering new types, not changing the core.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models import IssuedItem


@dataclass
class BuiltItem:
    payload: dict          # sent to the client
    answer: dict           # kept on the server


@dataclass
class Grade:
    correct: bool
    score: float
    chosen_word_ids: list[int] = field(default_factory=list)  # wrong words picked (for confusions)
    self_rating: int = 0
    feedback: dict[str, Any] = field(default_factory=dict)    # extra data shown after answering


class ItemType(ABC):
    name: str
    section: str
    hint_available: bool = False

    @abstractmethod
    def build(self, db: Session, user_id: str, subject: Any) -> BuiltItem | None:
        """Create a question about `subject`, or None if this type can't be built for it."""

    @abstractmethod
    async def grade(self, db: Session, item: IssuedItem, response: dict) -> Grade:
        """Grade a response against the stored answer."""

    def hint(self, item: IssuedItem) -> dict | None:
        return None


REGISTRY: dict[str, ItemType] = {}


def register(item_type: ItemType) -> ItemType:
    REGISTRY[item_type.name] = item_type
    return item_type


def get_item_type(name: str) -> ItemType:
    return REGISTRY[name]
