from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.errors import HANDLED, to_http
from app.application.festival_publication import PublicationResult, PublishFestival, UnpublishFestival
from app.database import get_db
from app.infrastructure.wiring import get_publish_festival, get_unpublish_festival
from app.schemas import FestivalCreate, FestivalRead, FestivalStateRead
from app.services.festival_service import FestivalService

router=APIRouter(prefix="/festivals",tags=["festivals"])

@router.get("",response_model=list[FestivalRead])
def list_festivals(db:Session=Depends(get_db)): 
    return FestivalService(db).list_festivals()

@router.post("",response_model=FestivalRead,status_code=201)
def create_festival(payload:FestivalCreate,db:Session=Depends(get_db)):
    try:
        return FestivalService(db).create_festival(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc))

def _out(result:PublicationResult,db:Session)->FestivalStateRead:
    from app.models import Festival as FestivalRow
    row=db.get(FestivalRow,result.festival.id)
    n=result.notification
    return FestivalStateRead(id=row.id,name=row.name,location=row.location,start_date=row.start_date,
                             end_date=row.end_date,status=result.festival.status.value,
                             notification=None if n is None else {"status":n.status.value,"detail":n.detail})

@router.post("/{festival_id}/publish",response_model=FestivalStateRead)
def publish_festival(festival_id:int,use_case:PublishFestival=Depends(get_publish_festival),db:Session=Depends(get_db)):
    try:
        return _out(use_case.execute(festival_id),db)
    except HANDLED as exc:
        raise to_http(exc)

@router.post("/{festival_id}/unpublish",response_model=FestivalStateRead)
def unpublish_festival(festival_id:int,use_case:UnpublishFestival=Depends(get_unpublish_festival),db:Session=Depends(get_db)):
    """Procédure explicite pour rouvrir un planning publié à la modification."""
    try:
        return _out(use_case.execute(festival_id),db)
    except HANDLED as exc:
        raise to_http(exc)
