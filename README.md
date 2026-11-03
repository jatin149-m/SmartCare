# Healthcare Appointment API

A backend REST API for a clinic: manage patients and doctors, book/cancel appointments
(with double-booking prevention) and expose a patient in a simplified HL7 FHIR format.
Built to mirror the kind of healthcare-IT backend work done at companies like HealthAsyst.

**Stack:** Python, FastAPI, SQLAlchemy (ORM), SQLite (swappable to MySQL), Pydantic, pytest, Git

## Run locally
```
python -m venv .venv
.venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs for interactive Swagger UI.

## Run tests
```
pytest -q
```

## Use MySQL instead of SQLite
```
pip install pymysql
set DATABASE_URL=mysql+pymysql://user:password@localhost:3306/healthdb
```

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | /health | service health check |
| POST/GET | /patients | create, list (search by name, pagination) |
| GET/PUT/DELETE | /patients/{id} | read, update, delete |
| POST/GET | /doctors | create, list (filter by specialty) |
| POST | /appointments | book (validates patient, doctor, future slot, no clash) |
| PATCH | /appointments/{id}/cancel | cancel and free the slot |
| GET | /patients/{id}/appointments | appointment history |
| GET | /fhir/Patient/{id} | FHIR-style Patient JSON |

## Deploy (free, Render)
1. Push this folder to a GitHub repo.
2. Render.com -> New -> Web Service -> connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Health check path: `/health`. Note: free tier SQLite resets on redeploy; use a hosted MySQL/Postgres for persistent data.

## Design notes
- Validation lives in Pydantic schemas (422 on bad input), business rules live in route handlers (404/409/400).
- One DB session per request via a FastAPI dependency; always closed.
- Patients with appointments cannot be deleted (protects medical history).

## Streamlit web app (live demo UI)
```
streamlit run streamlit_app.py
```
Uses the same models, validation and booking rules as the API (`app/services.py`).
Deploy on Streamlit Community Cloud: main file path = `streamlit_app.py`.
Note: SQLite data on the free tier resets when the app restarts; this is a demo.
