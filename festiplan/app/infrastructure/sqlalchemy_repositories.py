"""Adaptateurs SQLAlchemy : traduisent modèles ORM <-> objets du domaine."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.domain.scheduling import Concert, Festival, TimeSlot


def _to_concert(row: models.Concert) -> Concert:
    return Concert(
        id=row.id, festival_id=row.festival_id, artist_id=row.artist_id, stage_id=row.stage_id,
        slot=TimeSlot(row.start_time, row.end_time), status=row.status,
    )


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
        if row is None:
            return None
        return Festival(id=row.id, name=row.name, period=TimeSlot(row.start_date, row.end_date), status=row.status)
