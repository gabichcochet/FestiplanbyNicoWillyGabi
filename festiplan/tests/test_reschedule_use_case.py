"""Tests unitaires du cas d'utilisation : ni base de données, ni HTTP.

Les ports sont remplacés par des faux en mémoire, ce qui rend les tests
instantanés et centrés sur les règles métier.
"""
from datetime import datetime

import pytest

from app.application.ports import NotificationFailed
from app.application.reschedule_concert import ConcertNotFound, RescheduleConcert, RescheduleConcertCommand
from app.domain.scheduling import (
    Concert, ConcertNotReschedulable, Festival, InvalidTimeSlot,
    OutsideFestivalPeriod, SchedulingConflict, TimeSlot,
)


def dt(day, hour, minute=0):
    return datetime(2027, 6, day, hour, minute)


class InMemoryConcerts:
    def __init__(self, *concerts):
        self.items = {c.id: c for c in concerts}
        self.saved = []

    def get(self, concert_id):
        return self.items.get(concert_id)

    def list_for_festival(self, festival_id):
        return [c for c in self.items.values() if c.festival_id == festival_id]

    def save(self, concert):
        self.saved.append(concert.id)


class InMemoryFestivals:
    def __init__(self, *festivals):
        self.items = {f.id: f for f in festivals}

    def get(self, festival_id):
        return self.items.get(festival_id)


class SpyNotifier:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def notify_schedule_change(self, concert_id, message):
        if self.fail:
            raise NotificationFailed("panne simulée")
        self.sent.append(concert_id)


def make(festival_status="preparation", notifier=None, extra=()):
    festival = Festival(1, "Hellforge", TimeSlot(dt(18, 10), dt(20, 23, 59)), festival_status)
    c1 = Concert(1, 1, artist_id=10, stage_id=100, slot=TimeSlot(dt(18, 15), dt(18, 16)), status="scheduled")
    c2 = Concert(2, 1, artist_id=20, stage_id=100, slot=TimeSlot(dt(18, 17), dt(18, 18)), status="scheduled")
    concerts = InMemoryConcerts(c1, c2, *extra)
    notifier = notifier or SpyNotifier()
    return RescheduleConcert(concerts, InMemoryFestivals(festival), notifier), concerts, notifier


def cmd(start, end, concert_id=1):
    return RescheduleConcertCommand(concert_id, start, end)


def test_moves_concert_saves_and_notifies():
    use_case, concerts, notifier = make()
    result = use_case.execute(cmd(dt(19, 20), dt(19, 21)))
    assert result.slot == TimeSlot(dt(19, 20), dt(19, 21))
    assert concerts.saved == [1]
    assert notifier.sent == [1]


def test_unknown_concert():
    use_case, _, _ = make()
    with pytest.raises(ConcertNotFound):
        use_case.execute(cmd(dt(19, 20), dt(19, 21), concert_id=42))


def test_invalid_slot():
    use_case, concerts, _ = make()
    with pytest.raises(InvalidTimeSlot):
        use_case.execute(cmd(dt(19, 21), dt(19, 20)))
    assert concerts.saved == []


def test_stage_conflict():
    use_case, concerts, notifier = make()
    with pytest.raises(SchedulingConflict, match="scène"):
        use_case.execute(cmd(dt(18, 17, 30), dt(18, 18, 30)))
    assert concerts.saved == [] and notifier.sent == []


def test_artist_conflict_on_other_stage():
    other = Concert(3, 1, artist_id=10, stage_id=200, slot=TimeSlot(dt(19, 12), dt(19, 13)), status="scheduled")
    use_case, _, _ = make(extra=[other])
    with pytest.raises(SchedulingConflict, match="artiste"):
        use_case.execute(cmd(dt(19, 12, 30), dt(19, 13, 30)))


def test_adjacent_slot_is_not_a_conflict():
    use_case, _, _ = make()
    use_case.execute(cmd(dt(18, 16), dt(18, 17)))  # finit pile quand c2 commence


def test_outside_festival():
    use_case, _, _ = make()
    with pytest.raises(OutsideFestivalPeriod):
        use_case.execute(cmd(dt(25, 20), dt(25, 21)))


def test_published_festival_is_frozen():
    use_case, concerts, _ = make(festival_status="published")
    with pytest.raises(ConcertNotReschedulable):
        use_case.execute(cmd(dt(19, 20), dt(19, 21)))
    assert concerts.saved == []


def test_notification_failure_is_swallowed_after_save():
    use_case, concerts, _ = make(notifier=SpyNotifier(fail=True))
    use_case.execute(cmd(dt(19, 20), dt(19, 21)))
    assert concerts.saved == [1]
