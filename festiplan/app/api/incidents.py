from fastapi import APIRouter, Depends
from app.api.errors import HANDLED, to_http
from app.api.presenters import incident_out
from app.application.report_incident import ListIncidents, ReportIncident, ReportIncidentCommand
from app.infrastructure.wiring import get_list_incidents, get_report_incident
from app.schemas import IncidentCreate, IncidentRead

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=IncidentRead, status_code=201)
def create_incident(payload: IncidentCreate, use_case: ReportIncident = Depends(get_report_incident)):
    command = ReportIncidentCommand(payload.concert_id, payload.description, payload.occurred_at)
    try:
        return incident_out(use_case.execute(command))
    except HANDLED as exc:
        raise to_http(exc)


@router.get("", response_model=list[IncidentRead])
def list_incidents(concert_id: int | None = None, use_case: ListIncidents = Depends(get_list_incidents)):
    return [incident_out(i) for i in use_case.execute(concert_id)]
