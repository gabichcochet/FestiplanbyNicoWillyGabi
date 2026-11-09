"""Tests des cas d'utilisation de programmation et d'annulation avec des ports en mémoire."""
from datetime import datetime

import pytest

from app.application.cancel_concert import CancelConcert
from app.application.errors import ArtistNotFound, ConcertNotFound, FestivalNotFound, StageNotFound
from app.application.schedule_concert import ScheduleConcert, ScheduleConcertCommand
from app.domain.catalog import Artist, Capacity, EquipmentSet, Stage
from app.domain.scheduling import (
    Concert,
    Festival,
    InvalidTimeSlot,
    ScheduleLocked,
    TimeSlot,
)


def dt(day: int, hour: int) -> datetime:
    return datetime(2027, 6, day, hour)


class InMemoryFestivals:
    def __init__(self, *festivals):
        self.items = {festival.id: festival for festival in festivals}

    def get(self, festival_id):
        return self.items.get(festival_id)


class InMemoryArtists:
    def __init__(self, *artists):
        self.items = {artist.id: artist for artist in artists}

    def get(self, artist_id):
        return self.items.get(artist_id)


class InMemoryStages:
    def __init__(self, *stages):
        self.items = {stage.id: stage for stage in stages}

    def get(self, stage_id):
        return self.items.get(stage_id)


class InMemoryConcerts:
    def __init__(self, *concerts):
        self.items = {concert.id: concert for concert in concerts}
        self.added = []
        self.saved = []

    def get(self, concert_id):
        return self.items.get(concert_id)

    def list_for_festival(self, festival_id):
        return [concert for concert in self.items.values() if concert.festival_id == festival_id]

    def add(self, concert):
        concert.id = len(self.items) + 1
        self.items[concert.id] = concert
        self.added.append(concert)
        return concert

    def save(self, concert):
        self.saved.append(concert)


@pytest.fixture
def context():
    festival = Festival(1, "Hellforge", TimeSlot(dt(18, 10), dt(20, 23)))
    artist = Artist(10, "Iron Vow", "Heavy", EquipmentSet())
    stage = Stage(100, 1, "Mainstage", Capacity(50000), EquipmentSet())
    concerts = InMemoryConcerts()
    festivals = InMemoryFestivals(festival)
    artists = InMemoryArtists(artist)
    stages = InMemoryStages(stage)
    schedule = ScheduleConcert(festivals, artists, stages, concerts)
    return festival, concerts, schedule


def command(*, festival_id=1, artist_id=10, stage_id=100, start=None, end=None):
    return ScheduleConcertCommand(
        festival_id,
        artist_id,
        stage_id,
        start or dt(18, 15),
        end or dt(18, 16),
    )


def test_schedule_concert_uses_ports_and_persists_result(context):
    _, concerts, schedule = context

    result = schedule.execute(command())

    assert result.id == 1
    assert result.festival_id == 1
    assert result.artist_id == 10
    assert result.stage_id == 100
    assert concerts.added == [result]


@pytest.mark.parametrize(
    ("scheduled_command", "error"),
    [
        (command(festival_id=9), FestivalNotFound),
        (command(artist_id=9), ArtistNotFound),
        (command(stage_id=9), StageNotFound),
    ],
)
def test_schedule_concert_reports_missing_references(context, scheduled_command, error):
    _, concerts, schedule = context

    with pytest.raises(error):
        schedule.execute(scheduled_command)

    assert concerts.added == []


def test_invalid_slot_is_rejected_before_repository_access():
    class NoAccess:
        def get(self, identifier):
            pytest.fail("A repository was accessed for an invalid time slot")

    use_case = ScheduleConcert(NoAccess(), NoAccess(), NoAccess(), NoAccess())

    with pytest.raises(InvalidTimeSlot):
        use_case.execute(command(start=dt(18, 16), end=dt(18, 15)))


def test_cancel_concert_persists_cancellation_and_respects_publication(context):
    festival, concerts, _ = context
    scheduled = Concert(1, 1, 10, 100, TimeSlot(dt(18, 15), dt(18, 16)), "scheduled")
    concerts.items[scheduled.id] = scheduled
    cancel = CancelConcert(concerts, InMemoryFestivals(festival))

    result = cancel.execute(scheduled.id)

    assert result.is_cancelled
    assert concerts.saved == [result]

    festival.publish([])
    with pytest.raises(ScheduleLocked):
        cancel.execute(scheduled.id)
    assert concerts.saved == [result]


def test_cancel_unknown_concert_is_reported(context):
    festival, concerts, _ = context
    cancel = CancelConcert(concerts, InMemoryFestivals(festival))

    with pytest.raises(ConcertNotFound):
        cancel.execute(99)
