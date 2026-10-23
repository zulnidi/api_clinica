from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

NAME = Field(min_length=2, max_length=150)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr


class PatientIn(BaseModel):
    full_name: str = NAME
    document_id: str = Field(min_length=5, max_length=30, pattern=r"^[0-9A-Za-z-]+$")
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)


class PatientUpdate(BaseModel):
    full_name: str = NAME
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    document_id: str
    email: EmailStr
    phone: str | None


class DoctorIn(BaseModel):
    full_name: str = NAME
    specialty: str = Field(min_length=3, max_length=100)


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    specialty: str


class AppointmentIn(BaseModel):
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    start: datetime = Field(description="Inicio con zona horaria, p. ej. 2030-01-08T10:00:00-05:00")
    reason: str = Field(min_length=3, max_length=300)


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: int
    doctor_id: int
    start: datetime
    end: datetime
    reason: str
    status: str


class SlotsOut(BaseModel):
    doctor_id: int
    date: str
    slots: list[datetime]
