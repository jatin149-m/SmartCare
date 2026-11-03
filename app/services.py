"""Business rules shared by the REST API (app/main.py) and the Streamlit UI."""
from datetime import datetime
from sqlalchemy.orm import Session
from . import models


class BookingError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def book_appointment(db: Session, patient_id: int, doctor_id: int, slot: datetime, reason=None):
    if slot < datetime.now():
        raise BookingError(400, "Cannot book a slot in the past")
    if not db.get(models.Patient, patient_id):
        raise BookingError(404, "Patient not found")
    if not db.get(models.Doctor, doctor_id):
        raise BookingError(404, "Doctor not found")
    clash = db.query(models.Appointment).filter_by(
        doctor_id=doctor_id, slot=slot, status="booked").first()
    if clash:
        raise BookingError(409, "Doctor already booked at this time")
    appt = models.Appointment(patient_id=patient_id, doctor_id=doctor_id, slot=slot, reason=reason)
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt
