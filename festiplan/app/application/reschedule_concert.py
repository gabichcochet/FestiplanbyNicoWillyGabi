"""Cas d'utilisation : déplacer un concert."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from app.application.ports import ConcertRepository, FestivalRepository, NotificationFailed, Notifier
from app.domain.scheduling import Concert, TimeSlot

logger = logging.getLogger(__name__)


class ConcertNotFound(Exception):
    pass


@dataclass(frozen=True)
class RescheduleConcertCommand:
    concert_id: int
    start_time: datetime
    end_time: datetime


class RescheduleConcert:
    def __init__(self, concerts: ConcertRepository, festivals: FestivalRepository, notifier: Notifier):
        self.concerts = concerts
        self.festivals = festivals
        self.notifier = notifier

    def execute(self, command: RescheduleConcertCommand) -> Concert:
        concert = self.concerts.get(command.concert_id)
        if concert is None:
            raise ConcertNotFound("Concert introuvable")
        festival = self.festivals.get(concert.festival_id)
        if festival is None:  # incohérence de données, ne devrait pas arriver
            raise ConcertNotFound("Festival du concert introuvable")

        new_slot = TimeSlot(command.start_time, command.end_time)
        concert.reschedule(new_slot, festival, self.concerts.list_for_festival(festival.id))
        self.concerts.save(concert)

        # Effet secondaire : le déplacement est déjà acté, une panne d'envoi
        # ne doit pas le transformer en erreur pour l'appelant.
        try:
            self.notifier.notify_schedule_change(
                concert.id, f"Concert déplacé au {concert.slot.start.isoformat()}"
            )
        except NotificationFailed:
            logger.warning("Notification non envoyée pour le concert #%s", concert.id, exc_info=True)
        return concert
