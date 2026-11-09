"""Conversion des objets du domaine en réponses de l'API."""
from app.application.notifications import NotificationOutcome
from app.domain.catalog import Artist, Stage
from app.domain.incident import Incident
from app.domain.scheduling import Concert, Festival


def concert_out(c: Concert) -> dict:
    return {"id": c.id, "festival_id": c.festival_id, "artist_id": c.artist_id, "stage_id": c.stage_id,
            "start_time": c.slot.start, "end_time": c.slot.end, "status": c.status}


def notification_out(n: NotificationOutcome | None) -> dict | None:
    return None if n is None else {"status": n.status.value, "detail": n.detail}


def festival_out(f: Festival) -> dict:
    return {"id": f.id, "name": f.name, "location": f.location, "start_date": f.period.start,
            "end_date": f.period.end, "status": f.status.value}


def artist_out(a: Artist) -> dict:
    return {"id": a.id, "name": a.name, "genre": a.genre, "required_equipment": list(a.required_equipment.items)}


def stage_out(s: Stage) -> dict:
    return {"id": s.id, "festival_id": s.festival_id, "name": s.name, "capacity": s.capacity.value,
            "available_equipment": list(s.available_equipment.items)}


def incident_out(i: Incident) -> dict:
    return {"id": i.id, "concert_id": i.concert_id, "description": i.description.text,
            "occurred_at": i.occurred_at, "resolved": i.resolved}
