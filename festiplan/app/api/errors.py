"""Traduction des erreurs métier en réponses HTTP (le domaine ne connaît pas HTTP)."""
from fastapi import HTTPException

from app.application.errors import ArtistNotFound, ConcertNotFound, FestivalNotFound, StageNotFound
from app.domain.scheduling import (
    ConcertNotReschedulable, DomainError, InvalidFestivalTransition,
    ScheduleHasConflicts, ScheduleLocked, SchedulingConflict,
)

_HTTP_STATUS = {
    # Objet demandé introuvable
    ConcertNotFound: 404,
    FestivalNotFound: 404,
    ArtistNotFound: 404,
    StageNotFound: 404,
    # Conflit avec l'état actuel (planning publié, autre concert)
    SchedulingConflict: 409,
    ConcertNotReschedulable: 409,
    ScheduleLocked: 409,
    ScheduleHasConflicts: 409,
    InvalidFestivalTransition: 409,
}

# Toute autre DomainError (créneau invalide, hors période, équipement manquant,
# capacité, description...) est une donnée refusée : 400.
HANDLED = (ConcertNotFound, FestivalNotFound, ArtistNotFound, StageNotFound, DomainError)


def to_http(exc: Exception) -> HTTPException:
    return HTTPException(status_code=_HTTP_STATUS.get(type(exc), 400), detail=str(exc))
