"""Composition : branche les adaptateurs techniques sur les cas d'utilisation."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.festival_publication import PublishFestival, UnpublishFestival
from app.application.notifications import RetryPendingNotifications
from app.application.reschedule_concert import RescheduleConcert
from app.database import get_db
from app.infrastructure.email_notifier import EmailNotifier
from app.infrastructure.sqlalchemy_repositories import (
    SqlAlchemyConcertRepository, SqlAlchemyFestivalRepository, SqlAlchemyPendingNotificationStore,
)


def get_reschedule_concert(db: Session = Depends(get_db)) -> RescheduleConcert:
    return RescheduleConcert(SqlAlchemyConcertRepository(db), SqlAlchemyFestivalRepository(db),
                             EmailNotifier(), SqlAlchemyPendingNotificationStore(db))


def get_publish_festival(db: Session = Depends(get_db)) -> PublishFestival:
    return PublishFestival(SqlAlchemyFestivalRepository(db), EmailNotifier(), SqlAlchemyPendingNotificationStore(db))


def get_unpublish_festival(db: Session = Depends(get_db)) -> UnpublishFestival:
    return UnpublishFestival(SqlAlchemyFestivalRepository(db))


def get_retry_notifications(db: Session = Depends(get_db)) -> RetryPendingNotifications:
    return RetryPendingNotifications(EmailNotifier(), SqlAlchemyPendingNotificationStore(db))


def get_pending_store(db: Session = Depends(get_db)) -> SqlAlchemyPendingNotificationStore:
    return SqlAlchemyPendingNotificationStore(db)
