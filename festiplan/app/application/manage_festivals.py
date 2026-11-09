"""Cas d'utilisation : créer et lister les festivals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.ports import FestivalRepository
from app.domain.scheduling import Festival, FestivalStatus, TimeSlot


@dataclass(frozen=True)
class CreateFestivalCommand:
    name: str
    location: str
    start_date: datetime
    end_date: datetime


class CreateFestival:
    def __init__(self, festivals: FestivalRepository):
        self.festivals = festivals

    def execute(self, command: CreateFestivalCommand) -> Festival:
        period = TimeSlot(command.start_date, command.end_date)  # fin après début
        festival = Festival(id=None, name=command.name, period=period,
                            status=FestivalStatus.PREPARATION, location=command.location)
        return self.festivals.add(festival)


class ListFestivals:
    def __init__(self, festivals: FestivalRepository):
        self.festivals = festivals

    def execute(self) -> list[Festival]:
        return self.festivals.list()
