from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Concert
from app.schemas import ConcertCreate,ConcertRead,ConcertReschedule
from app.services.scheduling_service import SchedulingService
from app.application.reschedule_concert import ConcertNotFound,RescheduleConcert,RescheduleConcertCommand
from app.domain.scheduling import (ConcertNotReschedulable,DomainError,InvalidTimeSlot,
                                   OutsideFestivalPeriod,SchedulingConflict)
from app.infrastructure.email_notifier import EmailNotifier
from app.infrastructure.sqlalchemy_repositories import SqlAlchemyConcertRepository,SqlAlchemyFestivalRepository

router=APIRouter(prefix="/concerts",tags=["concerts"])

@router.get("",response_model=list[ConcertRead])
def list_concerts(festival_id:int,db:Session=Depends(get_db)):
    return SchedulingService(db).list_concerts(festival_id)

@router.get("/{concert_id}",response_model=ConcertRead)
def get_concert(concert_id:int,db:Session=Depends(get_db)):
    # Accès direct à SQLAlchemy depuis le contrôleur : défaut architectural.
    c=db.query(Concert).filter(Concert.id==concert_id).first()
    if c is None:
        raise HTTPException(status_code=404,detail="Concert introuvable")
    return c

@router.post("",response_model=ConcertRead,status_code=201)
def create_concert(payload:ConcertCreate,db:Session=Depends(get_db)):
    try:
        return SchedulingService(db).create_concert(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc))

def get_reschedule_concert(db:Session=Depends(get_db)) -> RescheduleConcert:
    """Composition : branche les adaptateurs techniques sur le cas d'utilisation."""
    return RescheduleConcert(SqlAlchemyConcertRepository(db),SqlAlchemyFestivalRepository(db),EmailNotifier())

# Traduction des erreurs métier en codes HTTP (le domaine ne connaît pas HTTP).
_HTTP_STATUS={
    ConcertNotFound:404,
    InvalidTimeSlot:400,
    OutsideFestivalPeriod:400,
    SchedulingConflict:409,
    ConcertNotReschedulable:409,
}

@router.patch("/{concert_id}/reschedule",response_model=ConcertRead)
def reschedule_concert(concert_id:int,payload:ConcertReschedule,use_case:RescheduleConcert=Depends(get_reschedule_concert)):
    command=RescheduleConcertCommand(concert_id,payload.start_time,payload.end_time)
    try:
        concert=use_case.execute(command)
    except (ConcertNotFound,DomainError) as exc:
        raise HTTPException(status_code=_HTTP_STATUS.get(type(exc),400),detail=str(exc))
    return ConcertRead(id=concert.id,festival_id=concert.festival_id,artist_id=concert.artist_id,
                       stage_id=concert.stage_id,start_time=concert.slot.start,end_time=concert.slot.end,
                       status=concert.status)

@router.post("/{concert_id}/cancel",response_model=ConcertRead)
def cancel_concert(concert_id:int,db:Session=Depends(get_db)):
    c=SchedulingService(db).cancel_concert(concert_id)
    if c is None:
        raise HTTPException(status_code=404,detail="Concert introuvable")
    return c

@router.get("/schedule/{festival_id}",response_model=list[ConcertRead])
def get_schedule(festival_id:int,db:Session=Depends(get_db)):
    return SchedulingService(db).get_schedule(festival_id)
