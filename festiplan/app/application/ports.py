"""Ports : ce dont les cas d'utilisation ont besoin, sans dire comment c'est fait."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.scheduling import Concert, Festival


class ConcertRepository(Protocol):
    def get(self, concert_id: int) -> Concert | None: ...
    def list_for_festival(self, festival_id: int) -> list[Concert]: ...
    def save(self, concert: Concert) -> None: ...


class FestivalRepository(Protocol):
    def get(self, festival_id: int) -> Festival | None: ...
    def save(self, festival: Festival) -> None: ...


class NotificationFailed(Exception):
    """Levée par un adaptateur de notification quand l'envoi échoue."""


class Notifier(Protocol):
    def send(self, subject: str, message: str) -> None: ...


@dataclass
class PendingNotification:
    id: int
    subject: str
    message: str
    attempts: int
    last_error: str
    created_at: datetime


class PendingNotificationStore(Protocol):
    """File des notifications à renvoyer (pas d'asynchrone : renvoi à la demande)."""
    def add(self, subject: str, message: str, error: str) -> PendingNotification: ...
    def list(self) -> list[PendingNotification]: ...
    def record_failure(self, notification_id: int, error: str) -> None: ...
    def remove(self, notification_id: int) -> None: ...
