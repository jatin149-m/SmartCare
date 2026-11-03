"""Pydantic schemas: validate incoming JSON and shape outgoing JSON."""
from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
import re


class PatientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    gender: Literal["male", "female", "other"]
    birth_date: date
    phone: str
    email: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v):
        if not re.fullmatch(r"\+?\d{10,13}", v):
            raise ValueError("phone must be 10-13 digits, optional leading +")
        return v

    @field_validator("birth_date")
    @classmethod
    def not_future(cls, v):
        if v > date.today():
            raise ValueError("birth_date cannot be in the future")
        return v

    @field_validator("email")
    @classmethod
    def email_ok(cls, v):
        if v is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("invalid email")
        return v


class PatientOut(PatientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class DoctorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    specialty: str = Field(min_length=2, max_length=60)


class DoctorOut(DoctorCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    slot: datetime
    reason: Optional[str] = Field(default=None, max_length=200)


class AppointmentOut(AppointmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
