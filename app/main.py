"""HealthAsyst-style healthcare backend: Patients, Doctors, Appointments + FHIR-style view.
Run:  uvicorn app.main:app --reload     Docs: http://127.0.0.1:8000/docs
"""
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models, schemas, services
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)  # creates tables if missing

app = FastAPI(title="Healthcare Appointment API", version="1.0")


@app.get("/health")
def health_check():
    """Used by hosting platforms to know the service is alive."""
    return {"status": "ok"}


# ---------------- Patients ----------------
@app.post("/patients", response_model=schemas.PatientOut, status_code=201)
def create_patient(p: schemas.PatientCreate, db: Session = Depends(get_db)):
    patient = models.Patient(**p.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A patient with this email already exists")
    db.refresh(patient)
    return patient


@app.get("/patients", response_model=List[schemas.PatientOut])
def list_patients(name: Optional[str] = None, skip: int = 0,
                  limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    q = db.query(models.Patient)
    if name:
        q = q.filter(models.Patient.first_name.ilike(f"%{name}%") |
                     models.Patient.last_name.ilike(f"%{name}%"))
    return q.offset(skip).limit(limit).all()  # pagination


@app.get("/patients/{patient_id}", response_model=schemas.PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    return patient


@app.put("/patients/{patient_id}", response_model=schemas.PatientOut)
def update_patient(patient_id: int, p: schemas.PatientCreate, db: Session = Depends(get_db)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    for k, v in p.model_dump().items():
        setattr(patient, k, v)
    db.commit()
    db.refresh(patient)
    return patient


@app.delete("/patients/{patient_id}", status_code=204)
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    if patient.appointments:
        raise HTTPException(409, "Patient has appointments; cancel them first")
    db.delete(patient)
    db.commit()


# ---------------- Doctors ----------------
@app.post("/doctors", response_model=schemas.DoctorOut, status_code=201)
def create_doctor(d: schemas.DoctorCreate, db: Session = Depends(get_db)):
    doctor = models.Doctor(**d.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@app.get("/doctors", response_model=List[schemas.DoctorOut])
def list_doctors(specialty: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Doctor)
    if specialty:
        q = q.filter(models.Doctor.specialty.ilike(f"%{specialty}%"))
    return q.all()


# ---------------- Appointments ----------------
@app.post("/appointments", response_model=schemas.AppointmentOut, status_code=201)
def book_appointment(a: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    try:
        return services.book_appointment(db, a.patient_id, a.doctor_id, a.slot, a.reason)
    except services.BookingError as e:
        raise HTTPException(e.status_code, e.message)


@app.patch("/appointments/{appt_id}/cancel", response_model=schemas.AppointmentOut)
def cancel_appointment(appt_id: int, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    appt.status = "cancelled"
    # record kept for audit; the slot is free again because clash check only looks at "booked"
    db.commit()
    db.refresh(appt)
    return appt


@app.get("/patients/{patient_id}/appointments", response_model=List[schemas.AppointmentOut])
def patient_history(patient_id: int, db: Session = Depends(get_db)):
    return db.query(models.Appointment).filter_by(patient_id=patient_id)\
             .order_by(models.Appointment.slot).all()


# ---------------- Interoperability (HL7 FHIR style) ----------------
@app.get("/fhir/Patient/{patient_id}")
def fhir_patient(patient_id: int, db: Session = Depends(get_db)):
    """Returns the patient in a simplified FHIR 'Patient' resource shape,
    showing how healthcare systems exchange data in a standard JSON format."""
    p = db.get(models.Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    return {
        "resourceType": "Patient",
        "id": str(p.id),
        "name": [{"family": p.last_name, "given": [p.first_name]}],
        "gender": p.gender,
        "birthDate": p.birth_date.isoformat(),
        "telecom": [{"system": "phone", "value": p.phone}] +
                   ([{"system": "email", "value": p.email}] if p.email else []),
    }
