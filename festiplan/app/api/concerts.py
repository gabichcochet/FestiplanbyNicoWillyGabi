from fastapi import APIRouter, Depends
from app.api.errors import HANDLED, to_http
from app.api.presenters import concert_out, notification_out
from app.application.cancel_concert import CancelConcert
from app.application.consult_schedule import GetConcert, GetFestivalSchedule
from app.application.reschedule_concert import RescheduleConcert, RescheduleConcertCommand
from app.application.schedule_concert import ScheduleConcert, ScheduleConcertCommand
from app.infrastructure.wiring import (
    get_cancel_concert, get_concert_query, get_festival_schedule, get_reschedule_concert, get_schedule_concert,
)
from app.schemas import ConcertCreate, ConcertRead, ConcertReschedule, ConcertRescheduleRead

router = APIRouter(prefix="/concerts", tags=["concerts"])


@router.get("", response_model=list[ConcertRead])
def list_concerts(festival_id: int, use_case: GetFestivalSchedule = Depends(get_festival_schedule)):
    return [concert_out(c) for c in use_case.execute(festival_id)]


@router.get("/schedule/{festival_id}", response_model=list[ConcertRead])
def get_schedule(festival_id: int, use_case: GetFestivalSchedule = Depends(get_festival_schedule)):
    return [concert_out(c) for c in use_case.execute(festival_id)]


@router.get("/{concert_id}", response_model=ConcertRead)
def get_concert(concert_id: int, use_case: GetConcert = Depends(get_concert_query)):
    try:
        return concert_out(use_case.execute(concert_id))
    except HANDLED as exc:
        raise to_http(exc)


@router.post("", response_model=ConcertRead, status_code=201)
def create_concert(payload: ConcertCreate, use_case: ScheduleConcert = Depends(get_schedule_concert)):
    command = ScheduleConcertCommand(payload.festival_id, payload.artist_id, payload.stage_id,
                                     payload.start_time, payload.end_time)
    try:
        return concert_out(use_case.execute(command))
    except HANDLED as exc:
        raise to_http(exc)


@router.patch("/{concert_id}/reschedule", response_model=ConcertRescheduleRead)
def reschedule_concert(concert_id: int, payload: ConcertReschedule,
                       use_case: RescheduleConcert = Depends(get_reschedule_concert)):
    try:
        result = use_case.execute(RescheduleConcertCommand(concert_id, payload.start_time, payload.end_time))
    except HANDLED as exc:
        raise to_http(exc)
    # 200 dès que le déplacement est enregistré ; l'état de la notification est explicite.
    return {**concert_out(result.concert), "notification": notification_out(result.notification)}


@router.post("/{concert_id}/cancel", response_model=ConcertRead)
def cancel_concert(concert_id: int, use_case: CancelConcert = Depends(get_cancel_concert)):
    try:
        return concert_out(use_case.execute(concert_id))
    except HANDLED as exc:
        raise to_http(exc)
