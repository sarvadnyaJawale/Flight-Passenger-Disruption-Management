import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

os.environ["DATA_DIR"] = os.path.join(os.path.dirname(__file__), "..", "..", "data")

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_flights_loaded(client):
    r = client.get("/api/dashboard/flights")
    assert r.status_code == 200
    flights = r.json()
    assert len(flights) > 0
    g9027 = [f for f in flights if f["flight_number"] == "G9027"]
    assert len(g9027) == 1


def test_full_disruption_pipeline(client):
    r = client.post("/api/disruptions", json={
        "flight_number": "G9027",
        "flight_date": "2027-03-04",
        "disruption_type": "cancellation",
        "reason": "technical",
    })
    assert r.status_code == 200
    disruption = r.json()
    assert disruption["flight_number"] == "G9027"
    assert disruption["affected_pax_count"] > 0
    did = disruption["id"]

    r = client.get(f"/api/disruptions/{did}/passengers")
    assert r.status_code == 200
    passengers = r.json()
    assert len(passengers) == disruption["affected_pax_count"]

    sorted_scores = [p["priority_score"] for p in passengers]
    assert sorted_scores == sorted(sorted_scores, reverse=True)

    r = client.get(f"/api/dashboard/kpis?disruption_id={did}")
    assert r.status_code == 200
    kpis = r.json()
    assert kpis["affected_pax_count"] == len(passengers)
    assert kpis["pending_count"] == len(passengers)

    r = client.post(f"/api/notifications/{did}/send", json={})
    assert r.status_code == 200
    notif = r.json()
    assert notif["sent_count"] == len(passengers)
    assert len(notif["deep_links"]) == len(passengers)

    deep_link = notif["deep_links"][0]["deep_link"]
    token = deep_link.split("/recover/")[-1]

    r = client.get(f"/api/recovery/{token}")
    assert r.status_code == 200
    recovery = r.json()
    assert recovery["pnr"] == notif["deep_links"][0]["pnr"]
    assert recovery["recovery_status"] == "options_viewed"

    if recovery["options"]:
        option_id = recovery["options"][0]["id"]
        r = client.post(f"/api/recovery/{token}/accept", json={
            "option_id": option_id,
            "action": "accept",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"

    r = client.get(f"/api/disruptions/{did}")
    assert r.status_code == 200
    assert r.json()["recovered_pax_count"] >= 0

    r = client.get("/api/disruptions")
    assert r.status_code == 200
    assert len(r.json()) >= 1
