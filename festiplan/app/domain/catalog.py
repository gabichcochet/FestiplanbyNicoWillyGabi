"""Domaine : scènes, artistes et leurs objets-valeurs.

Aucune dépendance à FastAPI, SQLAlchemy ou à la config.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.domain.scheduling import DomainError


class InvalidEquipment(DomainError):
    pass


class InvalidCapacity(DomainError):
    pass


@dataclass(frozen=True)
class EquipmentSet:
    """Ensemble de noms d'équipements (ordre d'origine conservé, sans doublon)."""
    items: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        cleaned: list[str] = []
        for raw in self.items:
            name = (raw or "").strip()
            if not name:
                raise InvalidEquipment("Un équipement doit avoir un nom")
            if name not in cleaned:
                cleaned.append(name)
        object.__setattr__(self, "items", tuple(cleaned))

    @classmethod
    def of(cls, names: Iterable[str]) -> EquipmentSet:
        return cls(tuple(names))

    def covers(self, required: EquipmentSet) -> bool:
        """R5 : tous les équipements requis sont disponibles."""
        return set(required.items) <= set(self.items)


@dataclass(frozen=True)
class Capacity:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidCapacity("La capacité d'une scène doit être strictement positive")


@dataclass
class Artist:
    id: int | None
    name: str
    genre: str
    required_equipment: EquipmentSet


@dataclass
class Stage:
    id: int | None
    festival_id: int
    name: str
    capacity: Capacity
    available_equipment: EquipmentSet
