from fastapi.testclient import TestClient

from support_ai.api import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_triage_accepts_subject_body() -> None:
    response = client.post("/triage", json={"subject": "How do I configure SSO?", "body": "Please help."})
    assert response.status_code == 200
    assert response.json()["category"] == "How-To"


def test_triage_accepts_free_text() -> None:
    response = client.post("/triage", json={"text": "We have a critical outage affecting all users."})
    assert response.status_code == 200
    assert response.json()["urgency"] == "P1"


def test_triage_rejects_empty_input() -> None:
    response = client.post("/triage", json={})
    assert response.status_code == 422


def test_triage_rejects_extra_fields() -> None:
    response = client.post("/triage", json={"subject": "hello", "category": "Billing"})
    assert response.status_code == 422


def test_account_not_found() -> None:
    response = client.get("/accounts/ACC-NOT-REAL/brief")
    assert response.status_code == 404
