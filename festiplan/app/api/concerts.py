from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Concert
from app.schemas import ConcertCreate,ConcertRead,ConcertReschedule,ConcertRescheduleRead
from app.services.scheduling_service import SchedulingService
from app.api.errors import HANDLED,to_http
from app.application.reschedule_concert import RescheduleConcert,RescheduleConcertCommand
from app.infrastructure.wiring import get_reschedule_concert

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
    except HANDLED as exc:
        raise to_http(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc))

@router.patch("/{concert_id}/reschedule",response_model=ConcertRescheduleRead)
def reschedule_concert(concert_id:int,payload:ConcertReschedule,use_case:RescheduleConcert=Depends(get_reschedule_concert)):
    try:
        result=use_case.execute(RescheduleConcertCommand(concert_id,payload.start_time,payload.end_time))
    except HANDLED as exc:
        raise to_http(exc)
    c=result.concert
    # 200 dès que le déplacement est enregistré ; l'état de la notification est explicite.
    return ConcertRescheduleRead(id=c.id,festival_id=c.festival_id,artist_id=c.artist_id,stage_id=c.stage_id,
                                 start_time=c.slot.start,end_time=c.slot.end,status=c.status,
                                 notification={"status":result.notification.status.value,
                                               "detail":result.notification.detail})

@router.post("/{concert_id}/cancel",response_model=ConcertRead)
def cancel_concert(concert_id:int,db:Session=Depends(get_db)):
    c=SchedulingService(db).cancel_concert(concert_id)
    if c is None:
        raise HTTPException(status_code=404,detail="Concert introuvable")
    return c

@router.get("/schedule/{festival_id}",response_model=list[ConcertRead])
def get_schedule(festival_id:int,db:Session=Depends(get_db)):
    return SchedulingService(db).get_schedule(festival_id)
