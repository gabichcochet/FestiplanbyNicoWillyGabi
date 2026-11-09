from fastapi import APIRouter, Depends
from app.api.errors import HANDLED, to_http
from app.api.presenters import festival_out, notification_out
from app.application.festival_publication import PublicationResult, PublishFestival, UnpublishFestival
from app.application.manage_festivals import CreateFestival, CreateFestivalCommand, ListFestivals
from app.infrastructure.wiring import (
    get_create_festival, get_list_festivals, get_publish_festival, get_unpublish_festival,
)
from app.schemas import FestivalCreate, FestivalRead, FestivalStateRead

router = APIRouter(prefix="/festivals", tags=["festivals"])


@router.get("", response_model=list[FestivalRead])
def list_festivals(use_case: ListFestivals = Depends(get_list_festivals)):
    return [festival_out(f) for f in use_case.execute()]


@router.post("", response_model=FestivalRead, status_code=201)
def create_festival(payload: FestivalCreate, use_case: CreateFestival = Depends(get_create_festival)):
    command = CreateFestivalCommand(payload.name, payload.location, payload.start_date, payload.end_date)
    try:
        return festival_out(use_case.execute(command))
    except HANDLED as exc:
        raise to_http(exc)


def _state(result: PublicationResult) -> dict:
    return {**festival_out(result.festival), "notification": notification_out(result.notification)}


@router.post("/{festival_id}/publish", response_model=FestivalStateRead)
def publish_festival(festival_id: int, use_case: PublishFestival = Depends(get_publish_festival)):
    """Publie le planning s'il ne contient aucun conflit (R8)."""
    try:
        return _state(use_case.execute(festival_id))
    except HANDLED as exc:
        raise to_http(exc)


@router.post("/{festival_id}/unpublish", response_model=FestivalStateRead)
def unpublish_festival(festival_id: int, use_case: UnpublishFestival = Depends(get_unpublish_festival)):
    """Procédure explicite pour rouvrir un planning publié à la modification."""
    try:
        return _state(use_case.execute(festival_id))
    except HANDLED as exc:
        raise to_http(exc)
