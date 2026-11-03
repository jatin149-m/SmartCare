import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
client = TestClient(app)

PATIENT = {"first_name": "Asha", "last_name": "Rao", "gender": "female",
           "birth_date": "1995-05-20", "phone": "9876543210", "email": "asha@example.com"}


def slot(days=2):
    return (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_fetch_patient():
    r = client.post("/patients", json=PATIENT)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.get(f"/patients/{pid}").json()["first_name"] == "Asha"


def test_duplicate_email_rejected():
    assert client.post("/patients", json=PATIENT).status_code == 409


def test_validation_errors():
    bad = {**PATIENT, "email": "x@y.com", "phone": "123"}
    assert client.post("/patients", json=bad).status_code == 422


def test_booking_flow_and_double_booking():
    doc = client.post("/doctors", json={"name": "Dr. Mehta", "specialty": "Cardiology"}).json()
    s = slot()
    body = {"patient_id": 1, "doctor_id": doc["id"], "slot": s, "reason": "Checkup"}
    first = client.post("/appointments", json=body)
    assert first.status_code == 201
    assert client.post("/appointments", json=body).status_code == 409  # double booking
    # cancel then rebook same slot works
    client.patch(f"/appointments/{first.json()['id']}/cancel")
    assert client.post("/appointments", json=body).status_code == 201


def test_past_slot_rejected():
    body = {"patient_id": 1, "doctor_id": 1, "slot": slot(-1)}
    assert client.post("/appointments", json=body).status_code == 400


def test_fhir_view():
    r = client.get("/fhir/Patient/1").json()
    assert r["resourceType"] == "Patient" and r["name"][0]["family"] == "Rao"


def test_delete_blocked_with_appointments():
    assert client.delete("/patients/1").status_code == 409
