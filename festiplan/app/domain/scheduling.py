"""Domaine : règles de planification des concerts.

Aucune dépendance à FastAPI, SQLAlchemy ou à la config : ce module se teste
avec de simples objets Python.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # uniquement pour les annotations : pas de dépendance circulaire
    from app.domain.catalog import Artist, Stage


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


class ScheduleHasConflicts(DomainError):
    """R8 : un planning ne peut pas être publié s'il contient des conflits."""


class StageNotInFestival(DomainError):
    pass


class MissingEquipment(DomainError):
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


SCHEDULED = "scheduled"
CANCELLED = "cancelled"


class FestivalStatus(str, Enum):
    """Cycle de vie du planning : preparation <-> published."""
    PREPARATION = "preparation"
    PUBLISHED = "published"


@dataclass
class Festival:
    id: int | None
    name: str
    period: TimeSlot
    status: FestivalStatus = FestivalStatus.PREPARATION
    location: str = field(default="")

    @property
    def is_published(self) -> bool:
        return self.status is FestivalStatus.PUBLISHED

    def ensure_schedule_editable(self) -> None:
        """Seul un planning en préparation accepte des ajouts ou déplacements."""
        if self.is_published:
            raise ScheduleLocked(
                "Le planning est publié : dépubliez le festival avant de le modifier"
            )

    def publish(self, concerts: Iterable[Concert]) -> None:
        """Publie le planning si tous ses concerts respectent les règles (R8)."""
        if self.status is not FestivalStatus.PREPARATION:
            raise InvalidFestivalTransition("Le festival est déjà publié")
        problems = schedule_problems(self, concerts)
        if problems:
            raise ScheduleHasConflicts("Publication impossible : " + " ; ".join(problems))
        self.status = FestivalStatus.PUBLISHED

    def unpublish(self) -> None:
        if self.status is not FestivalStatus.PUBLISHED:
            raise InvalidFestivalTransition("Le festival n'est pas publié")
        self.status = FestivalStatus.PREPARATION


@dataclass
class Concert:
    id: int | None
    festival_id: int
    artist_id: int
    stage_id: int
    slot: TimeSlot
    status: str

    @property
    def is_cancelled(self) -> bool:
        return self.status == CANCELLED

    @classmethod
    def schedule(cls, festival: Festival, artist: Artist, stage: Stage,
                 slot: TimeSlot, others: list[Concert]) -> Concert:
        """Programme un nouveau concert (R2, R3, R4 appartenance, R5, R6, R7)."""
        festival.ensure_schedule_editable()
        if stage.festival_id != festival.id:
            raise StageNotInFestival("La scène n'appartient pas à ce festival")
        if not stage.available_equipment.covers(artist.required_equipment):
            raise MissingEquipment("La scène ne dispose pas de tous les équipements requis")
        concert = cls(id=None, festival_id=festival.id, artist_id=artist.id, stage_id=stage.id,
                      slot=slot, status=SCHEDULED)
        concert._check_slot(slot, festival, others)
        return concert

    def reschedule(self, new_slot: TimeSlot, festival: Festival, others: list[Concert]) -> None:
        """Déplace le concert si toutes les règles métier sont respectées."""
        if self.is_cancelled:
            raise ConcertNotReschedulable("Un concert annulé ne peut pas être déplacé")
        festival.ensure_schedule_editable()
        self._check_slot(new_slot, festival, others)
        self.slot = new_slot

    def cancel(self, festival: Festival) -> None:
        """Annule le concert ; impossible sur un planning publié (R7)."""
        festival.ensure_schedule_editable()
        self.status = CANCELLED

    def _check_slot(self, slot: TimeSlot, festival: Festival, others: Iterable[Concert]) -> None:
        """Règles communes à tout placement d'un concert sur un créneau (R6, R2, R3)."""
        if not slot.is_within(festival.period):
            raise OutsideFestivalPeriod("Le concert doit se dérouler pendant le festival")
        for other in others:
            if other is self or (self.id is not None and other.id == self.id):
                continue
            if other.is_cancelled or not slot.overlaps(other.slot):
                continue
            if other.stage_id == self.stage_id:
                raise SchedulingConflict("Conflit : la scène est déjà occupée")
            if other.artist_id == self.artist_id:
                raise SchedulingConflict("Conflit : l'artiste est déjà programmé")


def schedule_problems(festival: Festival, concerts: Iterable[Concert]) -> list[str]:
    """Liste les violations de R2, R3 et R6 dans un planning (concerts annulés ignorés)."""
    active = [c for c in concerts if not c.is_cancelled]
    problems: list[str] = []
    for c in active:
        if not c.slot.is_within(festival.period):
            problems.append(f"le concert #{c.id} est hors des dates du festival")
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if not a.slot.overlaps(b.slot):
                continue
            if a.stage_id == b.stage_id:
                problems.append(f"les concerts #{a.id} et #{b.id} occupent la même scène en même temps")
            elif a.artist_id == b.artist_id:
                problems.append(f"l'artiste des concerts #{a.id} et #{b.id} joue deux fois en même temps")
    return problems
