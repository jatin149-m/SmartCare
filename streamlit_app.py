"""Streamlit front end for the Healthcare Appointment system.
Uses the same models, validation schemas and booking rules as the FastAPI backend.
Run:  streamlit run streamlit_app.py
"""
from datetime import datetime, date, time
import pandas as pd
import streamlit as st
from pydantic import ValidationError

from app import models, schemas, services
from app.database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)
st.set_page_config(page_title="Healthcare Appointment System", page_icon="🏥", layout="wide")


@st.cache_resource
def seed_demo_data():
    """Add a few doctors the first time so the app is not empty."""
    db = SessionLocal()
    try:
        if db.query(models.Doctor).count() == 0:
            db.add_all([models.Doctor(name="Dr. Anita Mehta", specialty="Cardiology"),
                        models.Doctor(name="Dr. Rohan Iyer", specialty="General Medicine"),
                        models.Doctor(name="Dr. Sana Khan", specialty="Pediatrics")])
            db.commit()
    finally:
        db.close()
    return True


seed_demo_data()
db = SessionLocal()

st.title("🏥 Healthcare Appointment System")
st.caption("Patients, doctors and appointments with validation and double-booking prevention. "
           "Demo data only - do not enter real patient information.")
page = st.sidebar.radio("Go to", ["Patients", "Doctors", "Book appointment", "Appointments", "FHIR view"])

if page == "Patients":
    st.subheader("Register a patient")
    with st.form("patient_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        first = c1.text_input("First name")
        last = c2.text_input("Last name")
        gender = c1.selectbox("Gender", ["female", "male", "other"])
        dob = c2.date_input("Birth date", value=date(2000, 1, 1), min_value=date(1900, 1, 1), max_value=date.today())
        phone = c1.text_input("Phone (10-13 digits)")
        email = c2.text_input("Email (optional)")
        if st.form_submit_button("Save patient"):
            try:
                data = schemas.PatientCreate(first_name=first, last_name=last, gender=gender,
                                             birth_date=dob, phone=phone, email=email or None)
                db.add(models.Patient(**data.model_dump()))
                db.commit()
                st.success("Patient saved")
            except ValidationError as e:
                db.rollback()
                for err in e.errors():
                    st.error(f"{err['loc'][0]}: {err['msg']}")
            except Exception:
                db.rollback()
                st.error("Could not save. A patient with this email may already exist.")
    st.subheader("Search patients")
    term = st.text_input("Search by name")
    q = db.query(models.Patient)
    if term:
        q = q.filter(models.Patient.first_name.ilike(f"%{term}%") | models.Patient.last_name.ilike(f"%{term}%"))
    rows = [{"ID": p.id, "Name": f"{p.first_name} {p.last_name}", "Gender": p.gender,
             "Birth date": p.birth_date, "Phone": p.phone, "Email": p.email} for p in q.limit(100)]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

elif page == "Doctors":
    st.subheader("Add a doctor")
    with st.form("doctor_form", clear_on_submit=True):
        name = st.text_input("Name")
        spec = st.text_input("Specialty")
        if st.form_submit_button("Save doctor"):
            try:
                d = schemas.DoctorCreate(name=name, specialty=spec)
                db.add(models.Doctor(**d.model_dump()))
                db.commit()
                st.success("Doctor saved")
            except ValidationError as e:
                for err in e.errors():
                    st.error(f"{err['loc'][0]}: {err['msg']}")
    f = st.text_input("Filter by specialty")
    q = db.query(models.Doctor)
    if f:
        q = q.filter(models.Doctor.specialty.ilike(f"%{f}%"))
    st.dataframe(pd.DataFrame([{"ID": d.id, "Name": d.name, "Specialty": d.specialty} for d in q]),
                 width="stretch", hide_index=True)

elif page == "Book appointment":
    st.subheader("Book an appointment")
    patients = db.query(models.Patient).all()
    doctors = db.query(models.Doctor).all()
    if not patients:
        st.info("Register a patient first (Patients page).")
    else:
        with st.form("book_form"):
            p = st.selectbox("Patient", patients, format_func=lambda x: f"{x.id} - {x.first_name} {x.last_name}")
            d = st.selectbox("Doctor", doctors, format_func=lambda x: f"{x.name} ({x.specialty})")
            day = st.date_input("Date", value=date.today())
            t = st.time_input("Time", value=time(10, 0), step=900)
            reason = st.text_input("Reason (optional)")
            if st.form_submit_button("Book"):
                try:
                    a = services.book_appointment(db, p.id, d.id, datetime.combine(day, t), reason or None)
                    st.success(f"Booked appointment #{a.id}")
                except services.BookingError as e:
                    st.error(e.message)

elif page == "Appointments":
    st.subheader("All appointments")
    appts = db.query(models.Appointment).order_by(models.Appointment.slot).all()
    st.dataframe(pd.DataFrame([{"ID": a.id, "Patient": f"{a.patient.first_name} {a.patient.last_name}",
                                "Doctor": a.doctor.name, "Slot": a.slot, "Reason": a.reason, "Status": a.status}
                               for a in appts]), width="stretch", hide_index=True)
    booked = [a for a in appts if a.status == "booked"]
    if booked:
        sel = st.selectbox("Cancel an appointment", booked,
                           format_func=lambda a: f"#{a.id} {a.patient.first_name} with {a.doctor.name} at {a.slot}")
        if st.button("Cancel selected"):
            sel.status = "cancelled"
            db.commit()
            st.success("Cancelled. The slot is free again.")
            st.rerun()

else:
    st.subheader("Patient in FHIR-style JSON")
    st.caption("FHIR is the standard healthcare systems use to exchange data.")
    patients = db.query(models.Patient).all()
    if patients:
        p = st.selectbox("Patient", patients, format_func=lambda x: f"{x.id} - {x.first_name} {x.last_name}")
        st.json({"resourceType": "Patient", "id": str(p.id),
                 "name": [{"family": p.last_name, "given": [p.first_name]}],
                 "gender": p.gender, "birthDate": p.birth_date.isoformat(),
                 "telecom": [{"system": "phone", "value": p.phone}] +
                            ([{"system": "email", "value": p.email}] if p.email else [])})
    else:
        st.info("No patients yet.")

db.close()
