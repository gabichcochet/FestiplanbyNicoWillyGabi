"""Tests unitaires du cas d'utilisation : ni base de données, ni HTTP.

Les ports sont remplacés par des faux en mémoire, ce qui rend les tests
instantanés et centrés sur les règles métier.
"""
from datetime import datetime

import pytest

from app.application.festival_publication import FestivalNotFound, PublishFestival, UnpublishFestival
from app.application.notifications import NotificationStatus, RetryPendingNotifications
from app.application.ports import NotificationFailed, PendingNotification
from app.application.reschedule_concert import ConcertNotFound, RescheduleConcert, RescheduleConcertCommand
from app.domain.scheduling import (
    Concert, Festival, FestivalStatus, InvalidFestivalTransition, InvalidTimeSlot,
    OutsideFestivalPeriod, ScheduleLocked, SchedulingConflict, TimeSlot,
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
        self.saved = []

    def get(self, festival_id):
        return self.items.get(festival_id)

    def save(self, festival):
        self.saved.append((festival.id, festival.status))


class SpyNotifier:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send(self, subject, message):
        if self.fail:
            raise NotificationFailed("panne simulée")
        self.sent.append(subject)


class InMemoryPending:
    def __init__(self):
        self.items = {}
        self._next = 1

    def add(self, subject, message, error):
        item = PendingNotification(self._next, subject, message, 1, error, dt(18, 0))
        self.items[item.id] = item
        self._next += 1
        return item

    def list(self):
        return list(self.items.values())

    def record_failure(self, notification_id, error):
        self.items[notification_id].attempts += 1
        self.items[notification_id].last_error = error

    def remove(self, notification_id):
        del self.items[notification_id]


def hellforge(status=FestivalStatus.PREPARATION):
    return Festival(1, "Hellforge", TimeSlot(dt(18, 10), dt(20, 23, 59)), status)


def make(festival_status=FestivalStatus.PREPARATION, notifier=None, extra=(), pending=None):
    festival = hellforge(festival_status)
    c1 = Concert(1, 1, artist_id=10, stage_id=100, slot=TimeSlot(dt(18, 15), dt(18, 16)), status="scheduled")
    c2 = Concert(2, 1, artist_id=20, stage_id=100, slot=TimeSlot(dt(18, 17), dt(18, 18)), status="scheduled")
    concerts = InMemoryConcerts(c1, c2, *extra)
    notifier = notifier or SpyNotifier()
    pending = pending if pending is not None else InMemoryPending()
    return RescheduleConcert(concerts, InMemoryFestivals(festival), notifier, pending), concerts, notifier


def cmd(start, end, concert_id=1):
    return RescheduleConcertCommand(concert_id, start, end)


def test_moves_concert_saves_and_notifies():
    use_case, concerts, notifier = make()
    result = use_case.execute(cmd(dt(19, 20), dt(19, 21)))
    assert result.concert.slot == TimeSlot(dt(19, 20), dt(19, 21))
    assert concerts.saved == [1]
    assert notifier.sent == ["Modification du concert #1"]
    assert result.notification.status is NotificationStatus.SENT


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


def test_overlapping_own_previous_slot_is_allowed():
    use_case, _, _ = make()
    use_case.execute(cmd(dt(18, 15, 30), dt(18, 16, 30)))


def test_published_festival_is_frozen():
    use_case, concerts, _ = make(festival_status=FestivalStatus.PUBLISHED)
    with pytest.raises(ScheduleLocked):
        use_case.execute(cmd(dt(19, 20), dt(19, 21)))
    assert concerts.saved == []


def test_notification_failure_keeps_the_move_and_queues_the_notification():
    pending = InMemoryPending()
    use_case, concerts, _ = make(notifier=SpyNotifier(fail=True), pending=pending)
    result = use_case.execute(cmd(dt(19, 20), dt(19, 21)))
    assert concerts.saved == [1]
    assert result.notification.status is NotificationStatus.PENDING_RETRY
    assert [p.subject for p in pending.list()] == ["Modification du concert #1"]


# --- Cycle de vie de la publication -----------------------------------------

def test_festival_lifecycle():
    f = hellforge()
    f.ensure_schedule_editable()
    f.publish([])
    assert f.is_published
    with pytest.raises(ScheduleLocked):
        f.ensure_schedule_editable()
    with pytest.raises(InvalidFestivalTransition):
        f.publish([])
    f.unpublish()
    assert f.status is FestivalStatus.PREPARATION
    with pytest.raises(InvalidFestivalTransition):
        f.unpublish()


def test_publish_use_case_saves_and_notifies():
    festivals, notifier, pending = InMemoryFestivals(hellforge()), SpyNotifier(), InMemoryPending()
    result = PublishFestival(festivals, InMemoryConcerts(), notifier, pending).execute(1)
    assert festivals.saved == [(1, FestivalStatus.PUBLISHED)]
    assert result.notification.status is NotificationStatus.SENT


def test_publish_with_failed_notification_is_still_published():
    festivals, pending = InMemoryFestivals(hellforge()), InMemoryPending()
    result = PublishFestival(festivals, InMemoryConcerts(), SpyNotifier(fail=True), pending).execute(1)
    assert result.festival.is_published
    assert len(pending.list()) == 1


def test_publish_unknown_festival():
    with pytest.raises(FestivalNotFound):
        PublishFestival(InMemoryFestivals(), InMemoryConcerts(), SpyNotifier(), InMemoryPending()).execute(9)


def test_unpublish_use_case():
    festivals = InMemoryFestivals(hellforge(FestivalStatus.PUBLISHED))
    UnpublishFestival(festivals).execute(1)
    assert festivals.saved == [(1, FestivalStatus.PREPARATION)]


# --- Renvoi des notifications en attente -------------------------------------

def test_retry_sends_and_removes_or_counts_failures():
    pending = InMemoryPending()
    pending.add("A", "a", "panne")
    pending.add("B", "b", "panne")

    report = RetryPendingNotifications(SpyNotifier(fail=True), pending).execute()
    assert (report.sent, report.still_pending) == (0, 2)
    assert [p.attempts for p in pending.list()] == [2, 2]

    notifier = SpyNotifier()
    report = RetryPendingNotifications(notifier, pending).execute()
    assert (report.sent, report.still_pending) == (2, 0)
    assert notifier.sent == ["A", "B"] and pending.list() == []
