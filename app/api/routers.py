from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.api import schemas
from app.api.dependencies import (
    current_user,
    get_appointment_service,
    get_auth_service,
    get_doctor_service,
    get_patient_service,
)
from app.application.services import AppointmentService, AuthService, DoctorService, PatientService

Limit = Query(50, ge=1, le=100)
Offset = Query(0, ge=0)

health = APIRouter(tags=["Salud"])
auth = APIRouter(prefix="/auth", tags=["Autenticación"])
patients = APIRouter(prefix="/patients", tags=["Pacientes"], dependencies=[Depends(current_user)])
doctors = APIRouter(prefix="/doctors", tags=["Médicos"], dependencies=[Depends(current_user)])
appointments = APIRouter(
    prefix="/appointments", tags=["Citas"], dependencies=[Depends(current_user)]
)


@health.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@auth.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(body: schemas.Credentials, service: AuthService = Depends(get_auth_service)):
    return service.register(body.email, body.password)


@auth.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.Credentials, service: AuthService = Depends(get_auth_service)):
    return schemas.TokenOut(access_token=service.login(body.email, body.password))


@patients.post("", response_model=schemas.PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(body: schemas.PatientIn, service: PatientService = Depends(get_patient_service)):
    return service.create(body.full_name, body.document_id, body.email, body.phone)


@patients.get("", response_model=list[schemas.PatientOut])
def list_patients(
    q: str | None = Query(None, description="Busca por nombre"),
    limit: int = Limit,
    offset: int = Offset,
    service: PatientService = Depends(get_patient_service),
):
    return service.list(query=q, limit=limit, offset=offset)


@patients.get("/{patient_id}", response_model=schemas.PatientOut)
def get_patient(patient_id: int, service: PatientService = Depends(get_patient_service)):
    return service.get(patient_id)


@patients.put("/{patient_id}", response_model=schemas.PatientOut)
def update_patient(
    patient_id: int,
    body: schemas.PatientUpdate,
    service: PatientService = Depends(get_patient_service),
):
    return service.update(patient_id, full_name=body.full_name, email=body.email, phone=body.phone)


@doctors.post("", response_model=schemas.DoctorOut, status_code=status.HTTP_201_CREATED)
def create_doctor(body: schemas.DoctorIn, service: DoctorService = Depends(get_doctor_service)):
    return service.create(body.full_name, body.specialty)


@doctors.get("", response_model=list[schemas.DoctorOut])
def list_doctors(
    specialty: str | None = None,
    limit: int = Limit,
    offset: int = Offset,
    service: DoctorService = Depends(get_doctor_service),
):
    return service.list(specialty=specialty, limit=limit, offset=offset)


@doctors.get("/{doctor_id}", response_model=schemas.DoctorOut)
def get_doctor(doctor_id: int, service: DoctorService = Depends(get_doctor_service)):
    return service.get(doctor_id)


@doctors.get("/{doctor_id}/availability", response_model=schemas.SlotsOut)
def availability(
    doctor_id: int,
    day: date = Query(alias="date", description="Día a consultar (AAAA-MM-DD)"),
    service: AppointmentService = Depends(get_appointment_service),
):
    return schemas.SlotsOut(
        doctor_id=doctor_id, date=day.isoformat(), slots=service.available_slots(doctor_id, day)
    )


@appointments.post("", response_model=schemas.AppointmentOut, status_code=status.HTTP_201_CREATED)
def schedule_appointment(
    body: schemas.AppointmentIn, service: AppointmentService = Depends(get_appointment_service)
):
    return service.schedule(
        patient_id=body.patient_id,
        doctor_id=body.doctor_id,
        start=body.start,
        reason=body.reason,
    )


@appointments.get("", response_model=list[schemas.AppointmentOut])
def list_appointments(
    doctor_id: int | None = None,
    patient_id: int | None = None,
    day: date | None = Query(None, alias="date"),
    limit: int = Limit,
    offset: int = Offset,
    service: AppointmentService = Depends(get_appointment_service),
):
    return service.list(
        doctor_id=doctor_id, patient_id=patient_id, day=day, limit=limit, offset=offset
    )


@appointments.get("/{appointment_id}", response_model=schemas.AppointmentOut)
def get_appointment(
    appointment_id: int, service: AppointmentService = Depends(get_appointment_service)
):
    return service.get(appointment_id)


@appointments.post("/{appointment_id}/cancel", response_model=schemas.AppointmentOut)
def cancel_appointment(
    appointment_id: int, service: AppointmentService = Depends(get_appointment_service)
):
    return service.cancel(appointment_id)


@appointments.post("/{appointment_id}/complete", response_model=schemas.AppointmentOut)
def complete_appointment(
    appointment_id: int, service: AppointmentService = Depends(get_appointment_service)
):
    return service.complete(appointment_id)
