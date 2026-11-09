"""Cas d'utilisation : annuler un concert."""
from __future__ import annotations

from app.application.errors import ConcertNotFound
from app.application.ports import ConcertRepository, FestivalRepository
from app.domain.scheduling import Concert


class CancelConcert:
    def __init__(self, concerts: ConcertRepository, festivals: FestivalRepository):
        self.concerts = concerts
        self.festivals = festivals

    def execute(self, concert_id: int) -> Concert:
        concert = self.concerts.get(concert_id)
        if concert is None:
            raise ConcertNotFound("Concert introuvable")
        festival = self.festivals.get(concert.festival_id)
        if festival is None:  # incohérence de données, ne devrait pas arriver
            raise ConcertNotFound("Festival du concert introuvable")

        concert.cancel(festival)  # R7 : refusé si le planning est publié
        self.concerts.save(concert)
        return concert
