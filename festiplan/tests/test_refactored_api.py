"""Étape 4 (vérifier que l'API fonctionne après chaque refactorisation) et étape 5
(défaut 3 avec l'option 2 : annulation bloquée, R8 à la republication).
Tests HTTP sur une base SQLite temporaire (voir conftest.py).
"""
from datetime import datetime

import pytest

from app import models
from app.database import SessionLocal


@pytest.fixture()
def fest(client):
    f = client.post("/festivals", json={
        "name": "Hellforge Open Air", "location": "Clisson",
        "start_date": "2027-06-18T10:00:00", "end_date": "2027-06-20T23:59:00",
    }).json()
    main = client.post("/stages", json={"festival_id": f["id"], "name": "Mainstage", "capacity": 50000,
                                        "available_equipment": ["large_rigging", "special_lighting"]}).json()
    valley = client.post("/stages", json={"festival_id": f["id"], "name": "Valley", "capacity": 8000,
                                          "available_equipment": ["special_lighting"]}).json()
    iron = client.post("/artists", json={"name": "Iron Vow", "genre": "Heavy",
                                         "required_equipment": ["large_rigging"]}).json()
    grave = client.post("/artists", json={"name": "Grave Choir", "genre": "Death"}).json()
    return {"id": f["id"], "main": main, "valley": valley, "iron": iron, "grave": grave}


def create(client, fest, artist, stage, start, end):
    return client.post("/concerts", json={"festival_id": fest["id"], "artist_id": fest[artist]["id"],
                                          "stage_id": fest[stage]["id"], "start_time": start, "end_time": end})


# --- Programmation -----------------------------------------------------------

def test_create_concert(client, fest):
    r = create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00")
    assert r.status_code == 201
    assert r.json()["status"] == "scheduled"
    assert client.get(f"/concerts/{r.json()['id']}").status_code == 200


def test_create_concert_stage_conflict_is_409(client, fest):
    create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00")
    r = create(client, fest, "grave", "main", "2027-06-18T15:30:00", "2027-06-18T16:30:00")
    assert r.status_code == 409 and "scène" in r.json()["detail"]


def test_create_concert_missing_equipment_is_400(client, fest):
    r = create(client, fest, "iron", "valley", "2027-06-18T15:00:00", "2027-06-18T16:00:00")
    assert r.status_code == 400 and "équipements" in r.json()["detail"]


def test_create_concert_outside_festival_is_400(client, fest):
    r = create(client, fest, "grave", "main", "2027-06-25T15:00:00", "2027-06-25T16:00:00")
    assert r.status_code == 400


def test_create_concert_with_unknown_artist_is_404(client, fest):
    r = client.post("/concerts", json={"festival_id": fest["id"], "artist_id": 999, "stage_id": fest["main"]["id"],
                                       "start_time": "2027-06-18T15:00:00", "end_time": "2027-06-18T16:00:00"})
    assert r.status_code == 404


def test_create_concert_on_stage_of_other_festival_is_400(client, fest):
    other = client.post("/festivals", json={"name": "Autre", "location": "Ailleurs",
                                            "start_date": "2027-06-18T10:00:00",
                                            "end_date": "2027-06-20T23:59:00"}).json()
    r = client.post("/concerts", json={"festival_id": other["id"], "artist_id": fest["grave"]["id"],
                                       "stage_id": fest["main"]["id"],
                                       "start_time": "2027-06-18T15:00:00", "end_time": "2027-06-18T16:00:00"})
    assert r.status_code == 400 and "n'appartient pas" in r.json()["detail"]


# --- Annulation --------------------------------------------------------------

def test_cancel_concert_frees_the_slot(client, fest):
    c = create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00").json()
    r = client.post(f"/concerts/{c['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert create(client, fest, "grave", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00").status_code == 201


def test_cancel_after_publication_is_refused(client, fest):  # R7 / défaut 3
    c = create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00").json()
    assert client.post(f"/festivals/{fest['id']}/publish").status_code == 200
    r = client.post(f"/concerts/{c['id']}/cancel")
    assert r.status_code == 409
    assert client.get(f"/concerts/{c['id']}").json()["status"] == "scheduled"


def test_cancel_unknown_concert_is_404(client):
    assert client.post("/concerts/999/cancel").status_code == 404


# --- Publication : R8 --------------------------------------------------------

def insert_concert_directly(festival_id, artist_id, stage_id, start, end):
    """Simule des données incohérentes déjà présentes en base (ex. importées avant la refacto)."""
    db = SessionLocal()
    try:
        db.add(models.Concert(festival_id=festival_id, artist_id=artist_id, stage_id=stage_id,
                              start_time=datetime.fromisoformat(start), end_time=datetime.fromisoformat(end),
                              status="scheduled"))
        db.commit()
    finally:
        db.close()


def test_publish_with_conflicting_concerts_is_refused(client, fest):  # R8
    create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00")
    insert_concert_directly(fest["id"], fest["grave"]["id"], fest["main"]["id"],
                            "2027-06-18T15:30:00", "2027-06-18T16:30:00")
    r = client.post(f"/festivals/{fest['id']}/publish")
    assert r.status_code == 409 and "même scène" in r.json()["detail"]
    status = next(f["status"] for f in client.get("/festivals").json() if f["id"] == fest["id"])
    assert status == "preparation"


def test_publish_after_fixing_the_conflict(client, fest):  # R8 + option 2
    create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00")
    insert_concert_directly(fest["id"], fest["grave"]["id"], fest["main"]["id"],
                            "2027-06-18T15:30:00", "2027-06-18T16:30:00")
    bad = client.get("/concerts", params={"festival_id": fest["id"]}).json()[-1]
    assert client.post(f"/concerts/{bad['id']}/cancel").status_code == 200
    assert client.post(f"/festivals/{fest['id']}/publish").status_code == 200


# --- Consultation ------------------------------------------------------------

def test_schedule_lists_active_concerts_in_order(client, fest):
    late = create(client, fest, "iron", "main", "2027-06-19T20:00:00", "2027-06-19T21:00:00").json()
    early = create(client, fest, "grave", "valley", "2027-06-18T12:00:00", "2027-06-18T13:00:00").json()
    cancelled = create(client, fest, "grave", "main", "2027-06-18T18:00:00", "2027-06-18T19:00:00").json()
    client.post(f"/concerts/{cancelled['id']}/cancel")
    ids = [c["id"] for c in client.get("/concerts", params={"festival_id": fest["id"]}).json()]
    assert ids == [early["id"], late["id"]]
    assert [c["id"] for c in client.get(f"/concerts/schedule/{fest['id']}").json()] == ids


def test_get_unknown_concert_is_404(client):
    assert client.get("/concerts/999").status_code == 404


# --- Festivals, scènes, artistes ---------------------------------------------

def test_festival_creation_and_listing(client, fest):
    festivals = client.get("/festivals").json()
    assert festivals[0]["location"] == "Clisson"
    assert festivals[0]["status"] == "preparation"


def test_stage_equipment_and_listing(client, fest):
    stages = client.get("/stages", params={"festival_id": fest["id"]}).json()
    assert [s["name"] for s in stages] == ["Mainstage", "Valley"]
    assert stages[0]["available_equipment"] == ["large_rigging", "special_lighting"]


def test_stage_for_unknown_festival_is_404(client):
    r = client.post("/stages", json={"festival_id": 999, "name": "Nulle part", "capacity": 10})
    assert r.status_code == 404


def test_artist_listing_is_sorted_and_keeps_equipment(client, fest):
    artists = client.get("/artists").json()
    assert [a["name"] for a in artists] == ["Grave Choir", "Iron Vow"]
    assert artists[1]["required_equipment"] == ["large_rigging"]


def test_blank_equipment_name_is_400(client):
    r = client.post("/artists", json={"name": "Blank Gear", "genre": "Noise", "required_equipment": ["  "]})
    assert r.status_code == 400


# --- Incidents ---------------------------------------------------------------

def test_report_incident_even_after_publication(client, fest):
    c = create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00").json()
    client.post(f"/festivals/{fest['id']}/publish")
    r = client.post("/incidents", json={"concert_id": c["id"], "description": "  Coupure de courant  "})
    assert r.status_code == 201
    assert r.json()["description"] == "Coupure de courant"
    listed = client.get("/incidents", params={"concert_id": c["id"]}).json()
    assert [i["id"] for i in listed] == [r.json()["id"]]


def test_incident_on_unknown_concert_is_404(client):
    r = client.post("/incidents", json={"concert_id": 999, "description": "Coupure de courant"})
    assert r.status_code == 404


def test_blank_incident_description_is_400(client, fest):  # R10 : vérifiée par le domaine, pas seulement Pydantic
    c = create(client, fest, "iron", "main", "2027-06-18T15:00:00", "2027-06-18T16:00:00").json()
    r = client.post("/incidents", json={"concert_id": c["id"], "description": "     "})
    assert r.status_code == 400
