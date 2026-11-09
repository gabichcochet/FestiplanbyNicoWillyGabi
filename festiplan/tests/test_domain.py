"""Tests unitaires du domaine, sans FastAPI ni base de données."""
from datetime import datetime

import pytest

from app.domain.catalog import (
    Capacity,
    EquipmentSet,
    InvalidCapacity,
    InvalidEquipment,
    Stage,
)
from app.domain.incident import IncidentDescription, InvalidIncidentDescription
from app.domain.scheduling import (
    CANCELLED,
    SCHEDULED,
    Concert,
    Festival,
    FestivalStatus,
    InvalidFestivalTransition,
    InvalidTimeSlot,
    MissingEquipment,
    OutsideFestivalPeriod,
    ScheduleHasConflicts,
    ScheduleLocked,
    SchedulingConflict,
    StageNotInFestival,
    TimeSlot,
    schedule_problems,
)
from app.domain.catalog import Artist


def dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2027, 6, day, hour, minute)


@pytest.fixture
def festival() -> Festival:
    return Festival(1, "Hellforge", TimeSlot(dt(18, 10), dt(20, 23, 59)))


@pytest.fixture
def artist() -> Artist:
    return Artist(10, "Iron Vow", "Heavy", EquipmentSet.of(["rigging"]))


@pytest.fixture
def stage() -> Stage:
    return Stage(100, 1, "Mainstage", Capacity(50000), EquipmentSet.of(["rigging", "lights"]))


def concert(concert_id: int, *, stage_id: int = 100, artist_id: int = 10,
            start: datetime | None = None, end: datetime | None = None,
            status: str = SCHEDULED) -> Concert:
    return Concert(
        concert_id,
        1,
        artist_id,
        stage_id,
        TimeSlot(start or dt(18, 15), end or dt(18, 16)),
        status,
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [(dt(18, 15), dt(18, 15)), (dt(18, 16), dt(18, 15))],
)
def test_time_slot_rejects_empty_or_reversed_intervals(start, end):
    with pytest.raises(InvalidTimeSlot):
        TimeSlot(start, end)


def test_time_slot_overlap_is_symmetric_and_adjacent_slots_do_not_overlap():
    first = TimeSlot(dt(18, 15), dt(18, 16))
    overlapping = TimeSlot(dt(18, 15, 30), dt(18, 16, 30))
    adjacent = TimeSlot(dt(18, 16), dt(18, 17))

    assert first.overlaps(overlapping)
    assert overlapping.overlaps(first)
    assert not first.overlaps(adjacent)
    assert adjacent.is_within(TimeSlot(dt(18, 10), dt(18, 23)))


def test_schedule_checks_festival_stage_equipment_and_conflicts(festival, artist, stage):
    scheduled = Concert.schedule(festival, artist, stage, TimeSlot(dt(18, 15), dt(18, 16)), [])
    assert scheduled.id is None
    assert scheduled.status == SCHEDULED

    with pytest.raises(OutsideFestivalPeriod):
        Concert.schedule(festival, artist, stage, TimeSlot(dt(21, 15), dt(21, 16)), [])

    with pytest.raises(StageNotInFestival):
        Concert.schedule(
            festival,
            artist,
            Stage(101, 2, "Other", Capacity(1000), EquipmentSet()),
            TimeSlot(dt(18, 15), dt(18, 16)),
            [],
        )

    with pytest.raises(MissingEquipment):
        Concert.schedule(
            festival,
            artist,
            Stage(101, 1, "Valley", Capacity(1000), EquipmentSet()),
            TimeSlot(dt(18, 15), dt(18, 16)),
            [],
        )


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        (concert(2), "scène"),
        (concert(2, stage_id=200), "artiste"),
    ],
)
def test_schedule_rejects_conflicts_with_active_concerts(festival, artist, stage, other, expected):
    with pytest.raises(SchedulingConflict, match=expected):
        Concert.schedule(festival, artist, stage, TimeSlot(dt(18, 15), dt(18, 16, 30)), [other])


def test_cancelled_concert_does_not_block_schedule(festival, artist, stage):
    cancelled = concert(2, status=CANCELLED)
    scheduled = Concert.schedule(festival, artist, stage, TimeSlot(dt(18, 15), dt(18, 16)), [cancelled])
    assert scheduled.status == SCHEDULED


def test_published_festival_locks_schedule_and_invalid_transitions(festival):
    festival.publish([])
    assert festival.status is FestivalStatus.PUBLISHED
    with pytest.raises(ScheduleLocked):
        festival.ensure_schedule_editable()
    with pytest.raises(InvalidFestivalTransition):
        festival.publish([])

    festival.unpublish()
    assert festival.status is FestivalStatus.PREPARATION
    with pytest.raises(InvalidFestivalTransition):
        festival.unpublish()


def test_publication_rejects_conflicting_schedule_and_ignores_cancelled_concerts(festival):
    festival.publish([concert(1), concert(2, start=dt(18, 16), end=dt(18, 17))])
    assert festival.is_published

    invalid_festival = Festival(2, "Invalid", festival.period)
    with pytest.raises(ScheduleHasConflicts, match="même scène"):
        invalid_festival.publish([
            concert(1),
            concert(2, status=CANCELLED),
            concert(3, start=dt(18, 15, 30), end=dt(18, 16, 30)),
        ])
    assert invalid_festival.status is FestivalStatus.PREPARATION


def test_schedule_problems_reports_out_of_period_and_artist_conflicts(festival):
    problems = schedule_problems(
        festival,
        [
            concert(1, stage_id=100, artist_id=10, start=dt(18, 15), end=dt(18, 16)),
            concert(2, stage_id=200, artist_id=10, start=dt(18, 15, 30), end=dt(18, 16, 30)),
            concert(3, stage_id=300, artist_id=30, start=dt(21, 15), end=dt(21, 16)),
        ],
    )

    assert any("artiste" in problem for problem in problems)
    assert any("hors des dates" in problem for problem in problems)


def test_catalog_and_incident_value_objects_enforce_invariants():
    assert EquipmentSet.of([" rigging ", "rigging", "lights"]).items == ("rigging", "lights")
    assert EquipmentSet.of(["rigging", "lights"]).covers(EquipmentSet.of(["rigging"]))
    assert IncidentDescription("  Câble cassé  ").text == "Câble cassé"

    with pytest.raises(InvalidEquipment):
        EquipmentSet.of(["  "])
    with pytest.raises(InvalidCapacity):
        Capacity(0)
    with pytest.raises(InvalidIncidentDescription):
        IncidentDescription(" x ")
