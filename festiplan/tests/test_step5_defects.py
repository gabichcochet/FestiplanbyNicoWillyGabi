"""Étape 5 — tests d'acceptation des trois défauts initiaux (niveau HTTP)."""
import pytest

from app.config import settings


@pytest.fixture()
def fest(client):
    f = client.post("/festivals", json={
        "name": "Hellforge Open Air", "location": "Clisson",
        "start_date": "2027-06-18T10:00:00", "end_date": "2027-06-20T23:59:00",
    }).json()
    main = client.post("/stages", json={"festival_id": f["id"], "name": "Mainstage", "capacity": 50000}).json()
    war = client.post("/stages", json={"festival_id": f["id"], "name": "Warzone", "capacity": 20000}).json()
    iron = client.post("/artists", json={"name": "Iron Anvil", "genre": "Heavy"}).json()
    grave = client.post("/artists", json={"name": "Grave Choir", "genre": "Death"}).json()

    def concert(artist, stage, start, end):
        r = client.post("/concerts", json={"festival_id": f["id"], "artist_id": artist["id"],
                                           "stage_id": stage["id"], "start_time": start, "end_time": end})
        assert r.status_code == 201, r.text
        return r.json()

    return {
        "id": f["id"], "main": main, "war": war, "iron": iron, "grave": grave,
        # Mainstage : iron 15h-16h, grave 17h-18h ; Warzone : iron 20h-21h
        "iron_main": concert(iron, main, "2027-06-18T15:00:00", "2027-06-18T16:00:00"),
        "grave_main": concert(grave, main, "2027-06-18T17:00:00", "2027-06-18T18:00:00"),
        "iron_war": concert(iron, war, "2027-06-18T20:00:00", "2027-06-18T21:00:00"),
    }


def move(client, concert_id, start, end):
    return client.patch(f"/concerts/{concert_id}/reschedule", json={"start_time": start, "end_time": end})


def start_of(client, concert_id):
    return client.get(f"/concerts/{concert_id}").json()["start_time"]


# =========================================================================
# Défaut 1 — conflits de programmation
# =========================================================================

class TestDefect1Conflicts:
    def test_overlap_on_same_stage_is_refused(self, client, fest):
        r = move(client, fest["grave_main"]["id"], "2027-06-18T15:30:00", "2027-06-18T16:30:00")
        assert r.status_code == 409
        assert r.json()["detail"] == "Conflit : la scène est déjà occupée"
        assert start_of(client, fest["grave_main"]["id"]) == "2027-06-18T17:00:00"

    def test_artist_cannot_play_on_two_stages_at_once(self, client, fest):
        # iron joue sur la Warzone à 20h : on tente de déplacer son concert Mainstage à 20h30
        r = move(client, fest["iron_main"]["id"], "2027-06-18T20:30:00", "2027-06-18T21:30:00")
        assert r.status_code == 409
        assert r.json()["detail"] == "Conflit : l'artiste est déjà programmé"
        assert start_of(client, fest["iron_main"]["id"]) == "2027-06-18T15:00:00"

    def test_valid_move_is_accepted(self, client, fest):
        r = move(client, fest["grave_main"]["id"], "2027-06-19T17:00:00", "2027-06-19T18:00:00")
        assert r.status_code == 200
        assert r.json()["start_time"] == "2027-06-19T17:00:00"
        assert start_of(client, fest["grave_main"]["id"]) == "2027-06-19T17:00:00"

    def test_back_to_back_slots_are_not_a_conflict(self, client, fest):
        r = move(client, fest["grave_main"]["id"], "2027-06-18T16:00:00", "2027-06-18T17:00:00")
        assert r.status_code == 200

    def test_concert_can_overlap_its_own_previous_slot(self, client, fest):
        r = move(client, fest["iron_main"]["id"], "2027-06-18T15:30:00", "2027-06-18T16:30:00")
        assert r.status_code == 200


# =========================================================================
# Défaut 2 — notification en échec
# Règle retenue : le déplacement est la source de vérité. S'il est enregistré,
# la réponse est 200 et indique explicitement l'état de la notification ; une
# notification échouée est conservée en base pour être renvoyée.
# =========================================================================

class TestDefect2Notification:
    def test_successful_notification_is_reported(self, client, fest):
        r = move(client, fest["grave_main"]["id"], "2027-06-19T17:00:00", "2027-06-19T18:00:00")
        assert r.status_code == 200
        assert r.json()["notification"] == {"status": "sent", "detail": None}
        assert client.get("/notifications/pending").json() == []

    def test_failed_notification_returns_200_and_says_so(self, client, fest, monkeypatch):
        monkeypatch.setattr(settings, "fail_notifications", True)
        r = move(client, fest["grave_main"]["id"], "2027-06-19T17:00:00", "2027-06-19T18:00:00")
        assert r.status_code == 200
        body = r.json()
        assert body["start_time"] == "2027-06-19T17:00:00"
        assert body["notification"]["status"] == "pending_retry"
        assert "indisponible" in body["notification"]["detail"]
        # la modification est bien persistée
        assert start_of(client, fest["grave_main"]["id"]) == "2027-06-19T17:00:00"

    def test_failed_notification_is_kept_and_can_be_retried(self, client, fest, monkeypatch):
        monkeypatch.setattr(settings, "fail_notifications", True)
        move(client, fest["grave_main"]["id"], "2027-06-19T17:00:00", "2027-06-19T18:00:00")
        pending = client.get("/notifications/pending").json()
        assert len(pending) == 1
        assert pending[0]["subject"] == f"Modification du concert #{fest['grave_main']['id']}"
        assert pending[0]["attempts"] == 1

        # toujours en panne : la notification reste en attente
        r = client.post("/notifications/retry").json()
        assert r == {"sent": 0, "still_pending": 1}
        assert client.get("/notifications/pending").json()[0]["attempts"] == 2

        # service rétabli : elle part et disparaît de la file
        monkeypatch.setattr(settings, "fail_notifications", False)
        assert client.post("/notifications/retry").json() == {"sent": 1, "still_pending": 0}
        assert client.get("/notifications/pending").json() == []

    def test_refused_move_sends_no_notification(self, client, fest, monkeypatch):
        monkeypatch.setattr(settings, "fail_notifications", True)
        move(client, fest["grave_main"]["id"], "2027-06-18T15:30:00", "2027-06-18T16:30:00")
        assert client.get("/notifications/pending").json() == []

    def test_publication_with_failed_notification_is_not_a_500(self, client, fest, monkeypatch):
        monkeypatch.setattr(settings, "fail_notifications", True)
        r = client.post(f"/festivals/{fest['id']}/publish")
        assert r.status_code == 200
        assert r.json()["status"] == "published"
        assert r.json()["notification"]["status"] == "pending_retry"


# =========================================================================
# Défaut 3 — planning publié
# Règle retenue : un planning publié est figé. Un déplacement (ou un ajout)
# est refusé avec 409. Pour modifier, l'organisateur dépublie explicitement
# (retour en préparation), modifie, puis republie (ce qui renotifie).
# =========================================================================

class TestDefect3Publication:
    def test_new_festival_is_in_preparation(self, client, fest):
        assert client.get("/festivals").json()[0]["status"] == "preparation"

    def test_publish_changes_state(self, client, fest):
        r = client.post(f"/festivals/{fest['id']}/publish")
        assert r.status_code == 200
        assert r.json()["status"] == "published"
        assert r.json()["notification"]["status"] == "sent"

    def test_cannot_publish_twice(self, client, fest):
        client.post(f"/festivals/{fest['id']}/publish")
        r = client.post(f"/festivals/{fest['id']}/publish")
        assert r.status_code == 409

    def test_move_after_publication_is_refused(self, client, fest):
        client.post(f"/festivals/{fest['id']}/publish")
        r = move(client, fest["grave_main"]["id"], "2027-06-19T17:00:00", "2027-06-19T18:00:00")
        assert r.status_code == 409
        assert "publié" in r.json()["detail"]
        assert start_of(client, fest["grave_main"]["id"]) == "2027-06-18T17:00:00"

    def test_adding_concert_after_publication_is_refused(self, client, fest):
        client.post(f"/festivals/{fest['id']}/publish")
        r = client.post("/concerts", json={"festival_id": fest["id"], "artist_id": fest["grave"]["id"],
                                           "stage_id": fest["war"]["id"],
                                           "start_time": "2027-06-19T12:00:00", "end_time": "2027-06-19T13:00:00"})
        assert r.status_code == 409

    def test_unpublish_then_move_then_republish(self, client, fest):
        client.post(f"/festivals/{fest['id']}/publish")
        r = client.post(f"/festivals/{fest['id']}/unpublish")
        assert r.status_code == 200 and r.json()["status"] == "preparation"
        assert move(client, fest["grave_main"]["id"], "2027-06-19T17:00:00", "2027-06-19T18:00:00").status_code == 200
        assert client.post(f"/festivals/{fest['id']}/publish").status_code == 200

    def test_cannot_unpublish_a_festival_in_preparation(self, client, fest):
        assert client.post(f"/festivals/{fest['id']}/unpublish").status_code == 409

    def test_unpublish_unknown_festival_returns_404(self, client):
        assert client.post("/festivals/999/unpublish").status_code == 404
