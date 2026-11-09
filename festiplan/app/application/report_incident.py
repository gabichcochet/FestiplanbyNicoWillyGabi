"""Cas d'utilisation : déclarer et consulter les incidents."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.errors import ConcertNotFound
from app.application.ports import ConcertRepository, IncidentRepository
from app.domain.incident import Incident, IncidentDescription


@dataclass(frozen=True)
class ReportIncidentCommand:
    concert_id: int
    description: str
    occurred_at: datetime | None = None


class ReportIncident:
    """Toujours possible, même sur un planning publié : un incident ne modifie pas le planning."""

    def __init__(self, concerts: ConcertRepository, incidents: IncidentRepository):
        self.concerts = concerts
        self.incidents = incidents

    def execute(self, command: ReportIncidentCommand) -> Incident:
        description = IncidentDescription(command.description)  # R10 : description valide
        if self.concerts.get(command.concert_id) is None:        # R10 : concert existant
            raise ConcertNotFound("Concert introuvable")
        incident = Incident(id=None, concert_id=command.concert_id, description=description,
                            occurred_at=command.occurred_at)
        return self.incidents.add(incident)


class ListIncidents:
    def __init__(self, incidents: IncidentRepository):
        self.incidents = incidents

    def execute(self, concert_id: int | None = None) -> list[Incident]:
        return self.incidents.list(concert_id)
