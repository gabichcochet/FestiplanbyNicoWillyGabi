"""Cas d'utilisation : artistes et scènes."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.errors import FestivalNotFound
from app.application.ports import ArtistRepository, FestivalRepository, StageRepository
from app.domain.catalog import Artist, Capacity, EquipmentSet, Stage


@dataclass(frozen=True)
class CreateArtistCommand:
    name: str
    genre: str
    required_equipment: list[str] = field(default_factory=list)


class CreateArtist:
    def __init__(self, artists: ArtistRepository):
        self.artists = artists

    def execute(self, command: CreateArtistCommand) -> Artist:
        artist = Artist(id=None, name=command.name, genre=command.genre,
                        required_equipment=EquipmentSet.of(command.required_equipment))
        return self.artists.add(artist)


class ListArtists:
    def __init__(self, artists: ArtistRepository):
        self.artists = artists

    def execute(self) -> list[Artist]:
        return self.artists.list()


@dataclass(frozen=True)
class CreateStageCommand:
    festival_id: int
    name: str
    capacity: int
    available_equipment: list[str] = field(default_factory=list)


class CreateStage:
    def __init__(self, festivals: FestivalRepository, stages: StageRepository):
        self.festivals = festivals
        self.stages = stages

    def execute(self, command: CreateStageCommand) -> Stage:
        if self.festivals.get(command.festival_id) is None:
            raise FestivalNotFound("Festival introuvable")
        stage = Stage(id=None, festival_id=command.festival_id, name=command.name,
                      capacity=Capacity(command.capacity),
                      available_equipment=EquipmentSet.of(command.available_equipment))
        return self.stages.add(stage)


class ListStages:
    def __init__(self, stages: StageRepository):
        self.stages = stages

    def execute(self, festival_id: int) -> list[Stage]:
        return self.stages.list_for_festival(festival_id)
