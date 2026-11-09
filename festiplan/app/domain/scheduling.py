"""Domaine : règles de planification des concerts.

Aucune dépendance à FastAPI, SQLAlchemy ou à la config : ce module se teste
avec de simples objets Python.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


# --- Erreurs métier --------------------------------------------------------

class DomainError(Exception):
    """Violation d'une règle métier."""


class InvalidTimeSlot(DomainError):
    pass


class OutsideFestivalPeriod(DomainError):
    pass


class SchedulingConflict(DomainError):
    pass


class ConcertNotReschedulable(DomainError):
    pass


class ScheduleLocked(DomainError):
    """Le planning est publié : il ne peut pas être modifié."""


class InvalidFestivalTransition(DomainError):
    pass


# --- Objets métier ---------------------------------------------------------

@dataclass(frozen=True)
class TimeSlot:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise InvalidTimeSlot("La date de fin doit être postérieure à la date de début")

    def overlaps(self, other: TimeSlot) -> bool:
        return self.start < other.end and other.start < self.end

    def is_within(self, other: TimeSlot) -> bool:
        return other.start <= self.start and self.end <= other.end


CANCELLED = "cancelled"


class FestivalStatus(str, Enum):
    """Cycle de vie du planning : preparation <-> published."""
    PREPARATION = "preparation"
    PUBLISHED = "published"


@dataclass
class Festival:
    id: int
    name: str
    period: TimeSlot
    status: FestivalStatus

    @property
    def is_published(self) -> bool:
        return self.status is FestivalStatus.PUBLISHED

    def ensure_schedule_editable(self) -> None:
        """Seul un planning en préparation accepte des ajouts ou déplacements."""
        if self.is_published:
            raise ScheduleLocked(
                "Le planning est publié : dépubliez le festival avant de le modifier"
            )

    def publish(self) -> None:
        if self.status is not FestivalStatus.PREPARATION:
            raise InvalidFestivalTransition("Le festival est déjà publié")
        self.status = FestivalStatus.PUBLISHED

    def unpublish(self) -> None:
        if self.status is not FestivalStatus.PUBLISHED:
            raise InvalidFestivalTransition("Le festival n'est pas publié")
        self.status = FestivalStatus.PREPARATION


@dataclass
class Concert:
    id: int
    festival_id: int
    artist_id: int
    stage_id: int
    slot: TimeSlot
    status: str

    @property
    def is_cancelled(self) -> bool:
        return self.status == CANCELLED

    def reschedule(self, new_slot: TimeSlot, festival: Festival, others: list[Concert]) -> None:
        """Déplace le concert si toutes les règles métier sont respectées."""
        if self.is_cancelled:
            raise ConcertNotReschedulable("Un concert annulé ne peut pas être déplacé")
        festival.ensure_schedule_editable()
        if not new_slot.is_within(festival.period):
            raise OutsideFestivalPeriod("Le concert doit se dérouler pendant le festival")
        for other in others:
            if other.id == self.id or other.is_cancelled or not new_slot.overlaps(other.slot):
                continue
            if other.stage_id == self.stage_id:
                raise SchedulingConflict("Conflit : la scène est déjà occupée")
            if other.artist_id == self.artist_id:
                raise SchedulingConflict("Conflit : l'artiste est déjà programmé")
        self.slot = new_slot
