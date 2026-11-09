"""Cas d'utilisation : publier / dépublier le planning d'un festival."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.notifications import NotificationOutcome, notify_or_queue
from app.application.ports import FestivalRepository, Notifier, PendingNotificationStore
from app.domain.scheduling import Festival


class FestivalNotFound(Exception):
    pass


@dataclass(frozen=True)
class PublicationResult:
    festival: Festival
    notification: NotificationOutcome | None


class PublishFestival:
    def __init__(self, festivals: FestivalRepository, notifier: Notifier, pending: PendingNotificationStore):
        self.festivals = festivals
        self.notifier = notifier
        self.pending = pending

    def execute(self, festival_id: int) -> PublicationResult:
        festival = self.festivals.get(festival_id)
        if festival is None:
            raise FestivalNotFound("Festival introuvable")
        festival.publish()
        self.festivals.save(festival)
        outcome = notify_or_queue(
            self.notifier, self.pending,
            f"Publication du festival #{festival.id}",
            f"Le planning du festival {festival.name} a été publié.",
        )
        return PublicationResult(festival, outcome)


class UnpublishFestival:
    def __init__(self, festivals: FestivalRepository):
        self.festivals = festivals

    def execute(self, festival_id: int) -> PublicationResult:
        festival = self.festivals.get(festival_id)
        if festival is None:
            raise FestivalNotFound("Festival introuvable")
        festival.unpublish()
        self.festivals.save(festival)
        return PublicationResult(festival, None)
