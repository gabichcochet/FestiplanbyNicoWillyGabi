"""Cas d'utilisation : déplacer un concert."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.notifications import NotificationOutcome, notify_or_queue
from app.application.ports import ConcertRepository, FestivalRepository, Notifier, PendingNotificationStore
from app.domain.scheduling import Concert, TimeSlot


class ConcertNotFound(Exception):
    pass


@dataclass(frozen=True)
class RescheduleConcertCommand:
    concert_id: int
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class RescheduleConcertResult:
    concert: Concert
    notification: NotificationOutcome


class RescheduleConcert:
    def __init__(self, concerts: ConcertRepository, festivals: FestivalRepository,
                 notifier: Notifier, pending: PendingNotificationStore):
        self.concerts = concerts
        self.festivals = festivals
        self.notifier = notifier
        self.pending = pending

    def execute(self, command: RescheduleConcertCommand) -> RescheduleConcertResult:
        concert = self.concerts.get(command.concert_id)
        if concert is None:
            raise ConcertNotFound("Concert introuvable")
        festival = self.festivals.get(concert.festival_id)
        if festival is None:  # incohérence de données, ne devrait pas arriver
            raise ConcertNotFound("Festival du concert introuvable")

        new_slot = TimeSlot(command.start_time, command.end_time)
        concert.reschedule(new_slot, festival, self.concerts.list_for_festival(festival.id))
        self.concerts.save(concert)  # à partir d'ici, le déplacement est acté

        outcome = notify_or_queue(
            self.notifier, self.pending,
            f"Modification du concert #{concert.id}",
            f"Concert déplacé au {concert.slot.start.isoformat()}",
        )
        return RescheduleConcertResult(concert, outcome)
