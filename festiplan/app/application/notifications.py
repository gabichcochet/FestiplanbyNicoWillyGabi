"""Gestion des notifications, séparée de la réussite de l'opération métier.

Décision (défaut 2) : une notification est un effet secondaire. Quand
l'opération métier est enregistrée, on tente l'envoi ; en cas d'échec,
la notification est conservée dans une file pour être renvoyée plus tard
et l'appelant en est informé. L'opération métier n'est jamais annulée ni
transformée en erreur 500 à cause de la notification.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from app.application.ports import NotificationFailed, Notifier, PendingNotificationStore

logger = logging.getLogger(__name__)


class NotificationStatus(str, Enum):
    SENT = "sent"
    PENDING_RETRY = "pending_retry"


@dataclass(frozen=True)
class NotificationOutcome:
    status: NotificationStatus
    detail: str | None = None


def notify_or_queue(notifier: Notifier, pending: PendingNotificationStore,
                    subject: str, message: str) -> NotificationOutcome:
    try:
        notifier.send(subject, message)
        return NotificationOutcome(NotificationStatus.SENT)
    except NotificationFailed as exc:
        logger.warning("Notification en échec, mise en file : %s", subject, exc_info=True)
        pending.add(subject, message, str(exc))
        return NotificationOutcome(NotificationStatus.PENDING_RETRY, str(exc))


@dataclass(frozen=True)
class RetryReport:
    sent: int
    still_pending: int


class RetryPendingNotifications:
    def __init__(self, notifier: Notifier, pending: PendingNotificationStore):
        self.notifier = notifier
        self.pending = pending

    def execute(self) -> RetryReport:
        sent = failed = 0
        for item in self.pending.list():
            try:
                self.notifier.send(item.subject, item.message)
            except NotificationFailed as exc:
                self.pending.record_failure(item.id, str(exc))
                failed += 1
            else:
                self.pending.remove(item.id)
                sent += 1
        return RetryReport(sent=sent, still_pending=failed)
