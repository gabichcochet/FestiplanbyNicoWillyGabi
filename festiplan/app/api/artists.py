from fastapi import APIRouter, Depends
from app.api.errors import HANDLED, to_http
from app.api.presenters import artist_out
from app.application.manage_catalog import CreateArtist, CreateArtistCommand, ListArtists
from app.infrastructure.wiring import get_create_artist, get_list_artists
from app.schemas import ArtistCreate, ArtistRead

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("", response_model=list[ArtistRead])
def list_artists(use_case: ListArtists = Depends(get_list_artists)):
    return [artist_out(a) for a in use_case.execute()]


@router.post("", response_model=ArtistRead, status_code=201)
def create_artist(payload: ArtistCreate, use_case: CreateArtist = Depends(get_create_artist)):
    command = CreateArtistCommand(payload.name, payload.genre, payload.required_equipment)
    try:
        return artist_out(use_case.execute(command))
    except HANDLED as exc:
        raise to_http(exc)
