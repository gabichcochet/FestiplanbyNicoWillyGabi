"""Adaptateurs SQLAlchemy : traduisent modèles ORM <-> objets du domaine."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.application.ports import PendingNotification
from app.domain.catalog import Artist, Capacity, EquipmentSet, Stage
from app.domain.incident import Incident, IncidentDescription
from app.domain.scheduling import Concert, Festival, FestivalStatus, TimeSlot


# --- Traduction ORM <-> domaine ----------------------------------------------

def _equipment(csv: str) -> EquipmentSet:
    return EquipmentSet.of(x for x in csv.split(",") if x.strip())


def _csv(equipment: EquipmentSet) -> str:
    return ",".join(equipment.items)


def _to_concert(row: models.Concert) -> Concert:
    return Concert(
        id=row.id, festival_id=row.festival_id, artist_id=row.artist_id, stage_id=row.stage_id,
        slot=TimeSlot(row.start_time, row.end_time), status=row.status,
    )


def _to_festival(row: models.Festival) -> Festival:
    return Festival(id=row.id, name=row.name, period=TimeSlot(row.start_date, row.end_date),
                    status=FestivalStatus(row.status), location=row.location)


def _to_artist(row: models.Artist) -> Artist:
    return Artist(id=row.id, name=row.name, genre=row.genre, required_equipment=_equipment(row.required_equipment))


def _to_stage(row: models.Stage) -> Stage:
    return Stage(id=row.id, festival_id=row.festival_id, name=row.name, capacity=Capacity(row.capacity),
                 available_equipment=_equipment(row.available_equipment))


def _to_incident(row: models.Incident) -> Incident:
    return Incident(id=row.id, concert_id=row.concert_id, description=IncidentDescription(row.description),
                    occurred_at=row.occurred_at, resolved=row.resolved)


# --- Repositories ------------------------------------------------------------


class SqlAlchemyConcertRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, concert_id: int) -> Concert | None:
        row = self.db.get(models.Concert, concert_id)
        return _to_concert(row) if row else None

    def list_for_festival(self, festival_id: int) -> list[Concert]:
        rows = self.db.query(models.Concert).filter(models.Concert.festival_id == festival_id).all()
        return [_to_concert(r) for r in rows]

    def add(self, concert: Concert) -> Concert:
        row = models.Concert(festival_id=concert.festival_id, artist_id=concert.artist_id,
                             stage_id=concert.stage_id, start_time=concert.slot.start,
                             end_time=concert.slot.end, status=concert.status)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_concert(row)

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
        return _to_festival(row) if row else None

    def list(self) -> list[Festival]:
        rows = self.db.query(models.Festival).order_by(models.Festival.id).all()
        return [_to_festival(r) for r in rows]

    def add(self, festival: Festival) -> Festival:
        row = models.Festival(name=festival.name, location=festival.location,
                              start_date=festival.period.start, end_date=festival.period.end,
                              status=festival.status.value)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_festival(row)

    def save(self, festival: Festival) -> None:
        row = self.db.get(models.Festival, festival.id)
        row.status = festival.status.value
        self.db.commit()


class SqlAlchemyArtistRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, artist_id: int) -> Artist | None:
        row = self.db.get(models.Artist, artist_id)
        return _to_artist(row) if row else None

    def list(self) -> list[Artist]:
        rows = self.db.query(models.Artist).order_by(models.Artist.name).all()
        return [_to_artist(r) for r in rows]

    def add(self, artist: Artist) -> Artist:
        row = models.Artist(name=artist.name, genre=artist.genre, required_equipment=_csv(artist.required_equipment))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_artist(row)


class SqlAlchemyStageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, stage_id: int) -> Stage | None:
        row = self.db.get(models.Stage, stage_id)
        return _to_stage(row) if row else None

    def list_for_festival(self, festival_id: int) -> list[Stage]:
        rows = self.db.query(models.Stage).filter(models.Stage.festival_id == festival_id).order_by(models.Stage.id).all()
        return [_to_stage(r) for r in rows]

    def add(self, stage: Stage) -> Stage:
        row = models.Stage(festival_id=stage.festival_id, name=stage.name, capacity=stage.capacity.value,
                           available_equipment=_csv(stage.available_equipment))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_stage(row)


class SqlAlchemyIncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, incident: Incident) -> Incident:
        row = models.Incident(concert_id=incident.concert_id, description=incident.description.text,
                              resolved=incident.resolved)
        if incident.occurred_at is not None:
            row.occurred_at = incident.occurred_at
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_incident(row)

    def list(self, concert_id: int | None = None) -> list[Incident]:
        query = self.db.query(models.Incident)
        if concert_id is not None:
            query = query.filter(models.Incident.concert_id == concert_id)
        return [_to_incident(r) for r in query.order_by(models.Incident.occurred_at.desc()).all()]


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
