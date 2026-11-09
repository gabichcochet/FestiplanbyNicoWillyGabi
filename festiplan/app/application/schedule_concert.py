"""Cas d'utilisation : programmer un concert."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.errors import ArtistNotFound, FestivalNotFound, StageNotFound
from app.application.ports import ArtistRepository, ConcertRepository, FestivalRepository, StageRepository
from app.domain.scheduling import Concert, TimeSlot


@dataclass(frozen=True)
class ScheduleConcertCommand:
    festival_id: int
    artist_id: int
    stage_id: int
    start_time: datetime
    end_time: datetime


class ScheduleConcert:
    def __init__(self, festivals: FestivalRepository, artists: ArtistRepository,
                 stages: StageRepository, concerts: ConcertRepository):
        self.festivals = festivals
        self.artists = artists
        self.stages = stages
        self.concerts = concerts

    def execute(self, command: ScheduleConcertCommand) -> Concert:
        slot = TimeSlot(command.start_time, command.end_time)  # R1 : donnée invalide, avant tout accès
        # R4 : les objets référencés doivent exister.
        festival = self.festivals.get(command.festival_id)
        if festival is None:
            raise FestivalNotFound("Festival introuvable")
        artist = self.artists.get(command.artist_id)
        if artist is None:
            raise ArtistNotFound("Artiste introuvable")
        stage = self.stages.get(command.stage_id)
        if stage is None:
            raise StageNotFound("Scène introuvable")

        concert = Concert.schedule(festival, artist, stage, slot, self.concerts.list_for_festival(festival.id))
        return self.concerts.add(concert)
