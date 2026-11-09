"""Traduction des erreurs métier en réponses HTTP (le domaine ne connaît pas HTTP)."""
from fastapi import HTTPException

from app.application.festival_publication import FestivalNotFound
from app.application.reschedule_concert import ConcertNotFound
from app.domain.scheduling import (
    ConcertNotReschedulable, DomainError, InvalidFestivalTransition, InvalidTimeSlot,
    OutsideFestivalPeriod, ScheduleLocked, SchedulingConflict,
)

_HTTP_STATUS = {
    ConcertNotFound: 404,
    FestivalNotFound: 404,
    InvalidTimeSlot: 400,
    OutsideFestivalPeriod: 400,
    SchedulingConflict: 409,
    ConcertNotReschedulable: 409,
    ScheduleLocked: 409,
    InvalidFestivalTransition: 409,
}

HANDLED = (ConcertNotFound, FestivalNotFound, DomainError)


def to_http(exc: Exception) -> HTTPException:
    return HTTPException(status_code=_HTTP_STATUS.get(type(exc), 400), detail=str(exc))
