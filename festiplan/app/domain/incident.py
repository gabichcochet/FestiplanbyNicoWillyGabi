"""Domaine : incidents survenus pendant un concert."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.scheduling import DomainError


class InvalidIncidentDescription(DomainError):
    pass


@dataclass(frozen=True)
class IncidentDescription:
    """R10 : une description non vide (au moins 3 caractères utiles)."""
    text: str

    def __post_init__(self) -> None:
        cleaned = (self.text or "").strip()
        if len(cleaned) < 3:
            raise InvalidIncidentDescription("La description d'un incident doit contenir au moins 3 caractères")
        object.__setattr__(self, "text", cleaned)


@dataclass
class Incident:
    id: int | None
    concert_id: int
    description: IncidentDescription
    occurred_at: datetime | None
    resolved: bool = False
