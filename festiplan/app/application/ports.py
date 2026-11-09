"""Ports : ce dont les cas d'utilisation ont besoin, sans dire comment c'est fait."""
from __future__ import annotations

from typing import Protocol

from app.domain.scheduling import Concert, Festival


class ConcertRepository(Protocol):
    def get(self, concert_id: int) -> Concert | None: ...
    def list_for_festival(self, festival_id: int) -> list[Concert]: ...
    def save(self, concert: Concert) -> None: ...


class FestivalRepository(Protocol):
    def get(self, festival_id: int) -> Festival | None: ...


class NotificationFailed(Exception):
    """Levée par un adaptateur de notification quand l'envoi échoue."""


class Notifier(Protocol):
    def notify_schedule_change(self, concert_id: int, message: str) -> None: ...
