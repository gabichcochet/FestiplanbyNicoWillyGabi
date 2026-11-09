"""Adaptateurs SQLAlchemy : traduisent modèles ORM <-> objets du domaine."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.application.ports import PendingNotification
from app.domain.scheduling import Concert, Festival, FestivalStatus, TimeSlot


def _to_concert(row: models.Concert) -> Concert:
    return Concert(
        id=row.id, festival_id=row.festival_id, artist_id=row.artist_id, stage_id=row.stage_id,
        slot=TimeSlot(row.start_time, row.end_time), status=row.status,
    )


def to_festival(row: models.Festival) -> Festival:
    return Festival(id=row.id, name=row.name, period=TimeSlot(row.start_date, row.end_date),
                    status=FestivalStatus(row.status))


class SqlAlchemyConcertRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, concert_id: int) -> Concert | None:
        row = self.db.get(models.Concert, concert_id)
        return _to_concert(row) if row else None

    def list_for_festival(self, festival_id: int) -> list[Concert]:
        rows = self.db.query(models.Concert).filter(models.Concert.festival_id == festival_id).all()
        return [_to_concert(r) for r in rows]

    def save(self, concert: Concert) -> None:
        row = self.db.get(models.Concert, concert.id)
        row.start_time = concert.slot.start
        row.end_time = concert.slot.end
        row.status = concert.status
        self.db.commit()


class SqlAlchemyFestivalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, festival_id: int) -> Festival | None:
        row = self.db.get(models.Festival, festival_id)
        return to_festival(row) if row else None

    def save(self, festival: Festival) -> None:
        row = self.db.get(models.Festival, festival.id)
        row.status = festival.status.value
        self.db.commit()


def _to_pending(row: models.PendingNotification) -> PendingNotification:
    return PendingNotification(id=row.id, subject=row.subject, message=row.message,
                               attempts=row.attempts, last_error=row.last_error, created_at=row.created_at)


class SqlAlchemyPendingNotificationStore:
    def __init__(self, db: Session):
        self.db = db

    def add(self, subject: str, message: str, error: str) -> PendingNotification:
        row = models.PendingNotification(subject=subject, message=message, attempts=1, last_error=error)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_pending(row)

    def list(self) -> list[PendingNotification]:
        rows = self.db.query(models.PendingNotification).order_by(models.PendingNotification.id).all()
        return [_to_pending(r) for r in rows]

    def record_failure(self, notification_id: int, error: str) -> None:
        row = self.db.get(models.PendingNotification, notification_id)
        row.attempts += 1
        row.last_error = error
        self.db.commit()

    def remove(self, notification_id: int) -> None:
        row = self.db.get(models.PendingNotification, notification_id)
        self.db.delete(row)
        self.db.commit()
