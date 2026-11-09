"""Cas d'utilisation de consultation : un concert, le planning d'un festival."""
from __future__ import annotations

from app.application.errors import ConcertNotFound
from app.application.ports import ConcertRepository
from app.domain.scheduling import Concert


class GetConcert:
    def __init__(self, concerts: ConcertRepository):
        self.concerts = concerts

    def execute(self, concert_id: int) -> Concert:
        concert = self.concerts.get(concert_id)
        if concert is None:
            raise ConcertNotFound("Concert introuvable")
        return concert


class GetFestivalSchedule:
    """Planning d'un festival : concerts non annulés, dans l'ordre chronologique."""

    def __init__(self, concerts: ConcertRepository):
        self.concerts = concerts

    def execute(self, festival_id: int) -> list[Concert]:
        active = [c for c in self.concerts.list_for_festival(festival_id) if not c.is_cancelled]
        return sorted(active, key=lambda c: (c.slot.start, c.id))
