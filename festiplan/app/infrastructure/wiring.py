"""Composition : branche les adaptateurs techniques sur les cas d'utilisation.

C'est le seul module qui connaît à la fois les cas d'utilisation et les
adaptateurs concrets (SQLAlchemy, e-mail). Les routes reçoivent des cas
d'utilisation déjà assemblés via `Depends`, ce qui permet de les remplacer
dans les tests.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.cancel_concert import CancelConcert
from app.application.consult_schedule import GetConcert, GetFestivalSchedule
from app.application.festival_publication import PublishFestival, UnpublishFestival
from app.application.manage_catalog import CreateArtist, CreateStage, ListArtists, ListStages
from app.application.manage_festivals import CreateFestival, ListFestivals
from app.application.notifications import RetryPendingNotifications
from app.application.report_incident import ListIncidents, ReportIncident
from app.application.reschedule_concert import RescheduleConcert
from app.application.schedule_concert import ScheduleConcert
from app.database import get_db
from app.infrastructure.email_notifier import EmailNotifier
from app.infrastructure.sqlalchemy_repositories import (
    SqlAlchemyArtistRepository, SqlAlchemyConcertRepository, SqlAlchemyFestivalRepository,
    SqlAlchemyIncidentRepository, SqlAlchemyPendingNotificationStore, SqlAlchemyStageRepository,
)


# --- Concerts ------------------------------------------------------------------

def get_schedule_concert(db: Session = Depends(get_db)) -> ScheduleConcert:
    return ScheduleConcert(SqlAlchemyFestivalRepository(db), SqlAlchemyArtistRepository(db),
                           SqlAlchemyStageRepository(db), SqlAlchemyConcertRepository(db))


def get_reschedule_concert(db: Session = Depends(get_db)) -> RescheduleConcert:
    return RescheduleConcert(SqlAlchemyConcertRepository(db), SqlAlchemyFestivalRepository(db),
                             EmailNotifier(), SqlAlchemyPendingNotificationStore(db))


def get_cancel_concert(db: Session = Depends(get_db)) -> CancelConcert:
    return CancelConcert(SqlAlchemyConcertRepository(db), SqlAlchemyFestivalRepository(db))


def get_concert_query(db: Session = Depends(get_db)) -> GetConcert:
    return GetConcert(SqlAlchemyConcertRepository(db))


def get_festival_schedule(db: Session = Depends(get_db)) -> GetFestivalSchedule:
    return GetFestivalSchedule(SqlAlchemyConcertRepository(db))


# --- Festivals -----------------------------------------------------------------

def get_create_festival(db: Session = Depends(get_db)) -> CreateFestival:
    return CreateFestival(SqlAlchemyFestivalRepository(db))


def get_list_festivals(db: Session = Depends(get_db)) -> ListFestivals:
    return ListFestivals(SqlAlchemyFestivalRepository(db))


def get_publish_festival(db: Session = Depends(get_db)) -> PublishFestival:
    return PublishFestival(SqlAlchemyFestivalRepository(db), SqlAlchemyConcertRepository(db),
                           EmailNotifier(), SqlAlchemyPendingNotificationStore(db))


def get_unpublish_festival(db: Session = Depends(get_db)) -> UnpublishFestival:
    return UnpublishFestival(SqlAlchemyFestivalRepository(db))


# --- Artistes et scènes --------------------------------------------------------

def get_create_artist(db: Session = Depends(get_db)) -> CreateArtist:
    return CreateArtist(SqlAlchemyArtistRepository(db))


def get_list_artists(db: Session = Depends(get_db)) -> ListArtists:
    return ListArtists(SqlAlchemyArtistRepository(db))


def get_create_stage(db: Session = Depends(get_db)) -> CreateStage:
    return CreateStage(SqlAlchemyFestivalRepository(db), SqlAlchemyStageRepository(db))


def get_list_stages(db: Session = Depends(get_db)) -> ListStages:
    return ListStages(SqlAlchemyStageRepository(db))


# --- Incidents -----------------------------------------------------------------

def get_report_incident(db: Session = Depends(get_db)) -> ReportIncident:
    return ReportIncident(SqlAlchemyConcertRepository(db), SqlAlchemyIncidentRepository(db))


def get_list_incidents(db: Session = Depends(get_db)) -> ListIncidents:
    return ListIncidents(SqlAlchemyIncidentRepository(db))


# --- Notifications -------------------------------------------------------------

def get_retry_notifications(db: Session = Depends(get_db)) -> RetryPendingNotifications:
    return RetryPendingNotifications(EmailNotifier(), SqlAlchemyPendingNotificationStore(db))


def get_pending_store(db: Session = Depends(get_db)) -> SqlAlchemyPendingNotificationStore:
    return SqlAlchemyPendingNotificationStore(db)
