"""Tests HTTP du déplacement d'un concert (PATCH /concerts/{id}/reschedule).

Écrits AVANT la refactorisation :
- les tests "comportement existant" passaient déjà sur le code legacy et doivent
  continuer à passer (filet de sécurité contre les régressions) ;
- les tests "règles métier" décrivent les 3 scénarios du README ; ils échouaient
  sur le code legacy et la refactorisation doit les faire passer.
"""
import pytest

from app.config import settings


@pytest.fixture()
def festival(client):
    """Hellforge mini : 1 festival, 2 scènes, 2 artistes, 2 concerts le 18 juin."""
    f = client.post("/festivals", json={
        "name": "Hellforge Open Air", "location": "Clisson",
        "start_date": "2027-06-18T10:00:00", "end_date": "2027-06-20T23:59:00",
    }).json()
    main = client.post("/stages", json={"festival_id": f["id"], "name": "Mainstage", "capacity": 50000, "available_equipment": []}).json()
    war = client.post("/stages", json={"festival_id": f["id"], "name": "Warzone", "capacity": 20000, "available_equipment": []}).json()
    a1 = client.post("/artists", json={"name": "Iron Anvil", "genre": "Heavy"}).json()
    a2 = client.post("/artists", json={"name": "Grave Choir", "genre": "Death"}).json()

    def concert(artist, stage, start, end):
        r = client.post("/concerts", json={
            "festival_id": f["id"], "artist_id": artist["id"], "stage_id": stage["id"],
            "start_time": start, "end_time": end,
        })
        assert r.status_code == 201, r.text
        return r.json()

    c1 = concert(a1, main, "2027-06-18T15:00:00", "2027-06-18T16:00:00")
    c2 = concert(a2, main, "2027-06-18T17:00:00", "2027-06-18T18:00:00")
    return {"festival": f, "main": main, "war": war, "a1": a1, "a2": a2, "c1": c1, "c2": c2}


def reschedule(client, concert_id, start, end):
    return client.patch(f"/concerts/{concert_id}/reschedule", json={"start_time": start, "end_time": end})


# --- Comportement existant (doit être préservé) ----------------------------

def test_reschedule_on_free_slot_updates_concert(client, festival):
    r = reschedule(client, festival["c1"]["id"], "2027-06-19T20:00:00", "2027-06-19T21:00:00")
    assert r.status_code == 200
    body = r.json()
    assert body["start_time"] == "2027-06-19T20:00:00"
    assert body["end_time"] == "2027-06-19T21:00:00"
    # la modification est bien persistée
    assert client.get(f"/concerts/{festival['c1']['id']}").json()["start_time"] == "2027-06-19T20:00:00"


def test_reschedule_unknown_concert_returns_404(client):
    r = reschedule(client, 999, "2027-06-19T20:00:00", "2027-06-19T21:00:00")
    assert r.status_code == 404


def test_reschedule_end_before_start_returns_400(client, festival):
    r = reschedule(client, festival["c1"]["id"], "2027-06-19T21:00:00", "2027-06-19T20:00:00")
    assert r.status_code == 400


# --- Règles métier (scénarios du README) -----------------------------------

def test_reschedule_on_occupied_stage_is_refused(client, festival):
    """Scénario 1 : même scène, créneau qui chevauche c2."""
    r = reschedule(client, festival["c1"]["id"], "2027-06-18T17:30:00", "2027-06-18T18:30:00")
    assert r.status_code == 409
    assert "scène" in r.json()["detail"]
    # rien n'a été modifié
    assert client.get(f"/concerts/{festival['c1']['id']}").json()["start_time"] == "2027-06-18T15:00:00"


def test_reschedule_when_artist_already_plays_elsewhere_is_refused(client, festival):
    other = client.post("/concerts", json={
        "festival_id": festival["festival"]["id"], "artist_id": festival["a1"]["id"],
        "stage_id": festival["war"]["id"],
        "start_time": "2027-06-19T12:00:00", "end_time": "2027-06-19T13:00:00",
    }).json()
    r = reschedule(client, festival["c1"]["id"], "2027-06-19T12:30:00", "2027-06-19T13:30:00")
    assert r.status_code == 409
    assert "artiste" in r.json()["detail"]
    assert other["id"] != festival["c1"]["id"]


def test_reschedule_outside_festival_dates_is_refused(client, festival):
    r = reschedule(client, festival["c1"]["id"], "2027-06-25T20:00:00", "2027-06-25T21:00:00")
    assert r.status_code == 400


def test_reschedule_cancelled_concert_is_refused(client, festival):
    client.post(f"/concerts/{festival['c1']['id']}/cancel")
    r = reschedule(client, festival["c1"]["id"], "2027-06-19T20:00:00", "2027-06-19T21:00:00")
    assert r.status_code == 409


def test_reschedule_can_free_slot_of_cancelled_concert(client, festival):
    """Un concert annulé ne bloque pas le créneau."""
    client.post(f"/concerts/{festival['c2']['id']}/cancel")
    r = reschedule(client, festival["c1"]["id"], "2027-06-18T17:00:00", "2027-06-18T18:00:00")
    assert r.status_code == 200


def test_reschedule_of_published_festival_is_refused(client, festival):
    """Scénario 3 : le planning publié est figé pour l'endpoint ordinaire."""
    assert client.post(f"/festivals/{festival['festival']['id']}/publish").status_code == 200
    r = reschedule(client, festival["c1"]["id"], "2027-06-19T20:00:00", "2027-06-19T21:00:00")
    assert r.status_code == 409
    assert client.get(f"/concerts/{festival['c1']['id']}").json()["start_time"] == "2027-06-18T15:00:00"


def test_notification_failure_does_not_turn_saved_move_into_500(client, festival, monkeypatch):
    """Scénario 2 : la notification est un effet secondaire, pas une condition du déplacement."""
    monkeypatch.setattr(settings, "fail_notifications", True)
    r = reschedule(client, festival["c1"]["id"], "2027-06-19T20:00:00", "2027-06-19T21:00:00")
    assert r.status_code == 200
    assert client.get(f"/concerts/{festival['c1']['id']}").json()["start_time"] == "2027-06-19T20:00:00"
