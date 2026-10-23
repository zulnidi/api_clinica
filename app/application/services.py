"""Casos de uso. Cada servicio tiene una responsabilidad y recibe sus dependencias."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.application import ports
from app.domain import rules
from app.domain.entities import Appointment, AppointmentStatus, Doctor, Patient, User
from app.domain.errors import AuthenticationError, ConflictError, NotFoundError, ValidationError

MIN_PASSWORD_LENGTH = 8


class AuthService:
    def __init__(
        self, users: ports.UserRepository, hasher: ports.PasswordHasher, tokens: ports.TokenService
    ):
        self._users, self._hasher, self._tokens = users, hasher, tokens

    def register(self, email: str, password: str) -> User:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
            )
        email = email.strip().lower()
        if self._users.get_by_email(email):
            raise ConflictError("Ya existe un usuario con ese correo.")
        return self._users.add(User(None, email, self._hasher.hash(password)))

    def login(self, email: str, password: str) -> str:
        user = self._users.get_by_email(email.strip().lower())
        # Mismo mensaje para correo o contraseña incorrectos: no revela qué usuarios existen.
        if user is None or not self._hasher.verify(password, user.password_hash):
            raise AuthenticationError("Credenciales inválidas.")
        assert user.id is not None
        return self._tokens.issue(user.id)

    def authenticate(self, token: str) -> User:
        user = self._users.get(self._tokens.read(token))
        if user is None:
            raise AuthenticationError("Token inválido.")
        return user


class PatientService:
    def __init__(self, patients: ports.PatientRepository):
        self._patients = patients

    def create(self, full_name: str, document_id: str, email: str, phone: str | None) -> Patient:
        if self._patients.get_by_document(document_id):
            raise ConflictError("Ya existe un paciente con ese documento.")
        return self._patients.add(Patient(None, full_name.strip(), document_id, email, phone))

    def get(self, patient_id: int) -> Patient:
        patient = self._patients.get(patient_id)
        if patient is None:
            raise NotFoundError("Paciente no encontrado.")
        return patient

    def update(self, patient_id: int, *, full_name: str, email: str, phone: str | None) -> Patient:
        patient = self.get(patient_id)
        return self._patients.update(
            replace(patient, full_name=full_name.strip(), email=email, phone=phone)
        )

    def list(self, *, query: str | None = None, limit: int = 50, offset: int = 0) -> list[Patient]:
        return self._patients.list(query=query, limit=limit, offset=offset)


class DoctorService:
    def __init__(self, doctors: ports.DoctorRepository):
        self._doctors = doctors

    def create(self, full_name: str, specialty: str) -> Doctor:
        return self._doctors.add(Doctor(None, full_name.strip(), specialty.strip()))

    def get(self, doctor_id: int) -> Doctor:
        doctor = self._doctors.get(doctor_id)
        if doctor is None:
            raise NotFoundError("Médico no encontrado.")
        return doctor

    def list(
        self, *, specialty: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Doctor]:
        return self._doctors.list(specialty=specialty, limit=limit, offset=offset)


class AppointmentService:
    def __init__(
        self,
        appointments: ports.AppointmentRepository,
        patients: PatientService,
        doctors: DoctorService,
        clock: ports.Clock,
        timezone: ZoneInfo,
    ):
        self._appointments = appointments
        self._patients = patients
        self._doctors = doctors
        self._clock = clock
        self._tz = timezone

    def schedule(
        self, *, patient_id: int, doctor_id: int, start: datetime, reason: str
    ) -> Appointment:
        self._patients.get(patient_id)  # lanza NotFoundError si no existe
        self._doctors.get(doctor_id)
        rules.validate_start(start, self._clock.now(), self._tz)
        end = start + rules.SLOT

        if self._appointments.find_scheduled_overlapping(
            start=start, end=end, doctor_id=doctor_id, patient_id=None
        ):
            raise ConflictError("El médico ya tiene una cita en ese horario.")
        if self._appointments.find_scheduled_overlapping(
            start=start, end=end, doctor_id=None, patient_id=patient_id
        ):
            raise ConflictError("El paciente ya tiene una cita en ese horario.")

        return self._appointments.add(
            Appointment(None, patient_id, doctor_id, start, end, reason.strip())
        )

    def get(self, appointment_id: int) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        if appointment is None:
            raise NotFoundError("Cita no encontrada.")
        return appointment

    def cancel(self, appointment_id: int) -> Appointment:
        appointment = self.get(appointment_id)
        rules.validate_cancellation(appointment, self._clock.now())
        return self._appointments.update(replace(appointment, status=AppointmentStatus.CANCELLED))

    def complete(self, appointment_id: int) -> Appointment:
        appointment = self.get(appointment_id)
        if appointment.status != AppointmentStatus.SCHEDULED:
            raise ConflictError("Solo se pueden completar citas programadas.")
        if appointment.start > self._clock.now():
            raise ConflictError("No se puede completar una cita que aún no ocurre.")
        return self._appointments.update(replace(appointment, status=AppointmentStatus.COMPLETED))

    def list(
        self,
        *,
        doctor_id: int | None = None,
        patient_id: int | None = None,
        day: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Appointment]:
        start = end = None
        if day is not None:
            start = datetime.combine(day, datetime.min.time(), tzinfo=self._tz)
            end = start + timedelta(days=1)
        return self._appointments.list(
            doctor_id=doctor_id,
            patient_id=patient_id,
            start=start,
            end=end,
            limit=limit,
            offset=offset,
        )

    def available_slots(self, doctor_id: int, day: date) -> list[datetime]:
        self._doctors.get(doctor_id)
        now = self._clock.now()
        taken = self.list(doctor_id=doctor_id, day=day, limit=1000)
        busy = [a for a in taken if a.status == AppointmentStatus.SCHEDULED]
        return [
            slot
            for slot in rules.daily_slots(day, self._tz)
            if slot > now
            and not any(rules.overlaps(slot, slot + rules.SLOT, a.start, a.end) for a in busy)
        ]
