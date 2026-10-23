from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.application.services import AppointmentService, AuthService, DoctorService, PatientService
from app.domain.entities import AppointmentStatus
from app.domain.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from tests.fakes import (
    NOW,
    FakeHasher,
    FakeTokens,
    FixedClock,
    InMemoryAppointments,
    InMemoryDoctors,
    InMemoryPatients,
    InMemoryUsers,
)

TZ = ZoneInfo("America/Bogota")
TUESDAY_10 = datetime(2030, 1, 8, 10, tzinfo=TZ)


@pytest.fixture
def auth():
    return AuthService(InMemoryUsers(), FakeHasher(), FakeTokens())


@pytest.fixture
def world():
    clock = FixedClock(NOW)
    patients, doctors = PatientService(InMemoryPatients()), DoctorService(InMemoryDoctors())
    appointments = AppointmentService(InMemoryAppointments(), patients, doctors, clock, TZ)
    ana = patients.create("Ana Pérez", "10001", "ana@example.com", None)
    luis = patients.create("Luis Gómez", "10002", "luis@example.com", None)
    doctor = doctors.create("Dra. Rojas", "Cardiología")
    return type(
        "World",
        (),
        dict(
            clock=clock,
            patients=patients,
            doctors=doctors,
            appointments=appointments,
            ana=ana,
            luis=luis,
            doctor=doctor,
        ),
    )


class TestAuth:
    def test_registra_y_autentica(self, auth):
        user = auth.register("  Ana@Example.com ", "clave-segura")
        assert user.email == "ana@example.com"
        token = auth.login("ana@example.com", "clave-segura")
        assert auth.authenticate(token).id == user.id

    def test_rechaza_contrasena_corta_y_correo_repetido(self, auth):
        with pytest.raises(ValidationError):
            auth.register("a@b.co", "corta")
        auth.register("a@b.co", "clave-segura")
        with pytest.raises(ConflictError):
            auth.register("A@B.co", "clave-segura")

    def test_credenciales_incorrectas(self, auth):
        auth.register("a@b.co", "clave-segura")
        for email, password in [("a@b.co", "otra-clave"), ("x@y.co", "clave-segura")]:
            with pytest.raises(AuthenticationError, match="Credenciales"):
                auth.login(email, password)

    def test_token_de_usuario_inexistente(self, auth):
        with pytest.raises(AuthenticationError):
            auth.authenticate("token-99")


class TestPatientsAndDoctors:
    def test_documento_duplicado(self, world):
        with pytest.raises(ConflictError):
            world.patients.create("Otra", "10001", "o@example.com", None)

    def test_get_update_y_list(self, world):
        updated = world.patients.update(
            world.ana.id, full_name=" Ana M. ", email="n@e.co", phone="3"
        )
        assert updated.full_name == "Ana M." and updated.document_id == "10001"
        assert [p.full_name for p in world.patients.list(query="luis")] == ["Luis Gómez"]
        with pytest.raises(NotFoundError):
            world.patients.get(999)

    def test_medicos(self, world):
        assert world.doctors.list(specialty="Cardiología") == [world.doctor]
        with pytest.raises(NotFoundError):
            world.doctors.get(999)


class TestAppointments:
    def schedule(self, world, patient=None, start=TUESDAY_10):
        return world.appointments.schedule(
            patient_id=(patient or world.ana).id,
            doctor_id=world.doctor.id,
            start=start,
            reason="Control",
        )

    def test_agenda_una_cita(self, world):
        appointment = self.schedule(world)
        assert appointment.end - appointment.start == timedelta(minutes=30)
        assert appointment.status == AppointmentStatus.SCHEDULED

    def test_no_permite_choques_de_medico_ni_de_paciente(self, world):
        self.schedule(world)
        with pytest.raises(ConflictError, match="médico"):
            self.schedule(world, patient=world.luis)
        other_doctor = world.doctors.create("Dr. Mora", "Pediatría")
        with pytest.raises(ConflictError, match="paciente"):
            world.appointments.schedule(
                patient_id=world.ana.id, doctor_id=other_doctor.id, start=TUESDAY_10, reason="Otro"
            )

    def test_paciente_o_medico_inexistente(self, world):
        with pytest.raises(NotFoundError):
            world.appointments.schedule(patient_id=99, doctor_id=1, start=TUESDAY_10, reason="x")
        with pytest.raises(NotFoundError):
            world.appointments.schedule(patient_id=1, doctor_id=99, start=TUESDAY_10, reason="x")

    def test_cancela_y_libera_el_horario(self, world):
        appointment = self.schedule(world)
        assert world.appointments.cancel(appointment.id).status == AppointmentStatus.CANCELLED
        self.schedule(world, patient=world.luis)  # el horario quedó libre
        with pytest.raises(ConflictError):
            world.appointments.cancel(appointment.id)  # ya cancelada

    def test_cancelar_con_poca_anticipacion(self, world):
        appointment = self.schedule(world)
        world.clock.advance_to(TUESDAY_10 - timedelta(hours=1))
        with pytest.raises(ConflictError, match="2 horas"):
            world.appointments.cancel(appointment.id)

    def test_completar(self, world):
        appointment = self.schedule(world)
        with pytest.raises(ConflictError, match="aún no ocurre"):
            world.appointments.complete(appointment.id)
        world.clock.advance_to(TUESDAY_10 + timedelta(hours=1))
        assert world.appointments.complete(appointment.id).status == AppointmentStatus.COMPLETED
        with pytest.raises(ConflictError):
            world.appointments.complete(appointment.id)

    def test_listado_con_filtros(self, world):
        self.schedule(world)
        assert len(world.appointments.list(day=date(2030, 1, 8))) == 1
        assert world.appointments.list(day=date(2030, 1, 9)) == []
        assert len(world.appointments.list(patient_id=world.ana.id)) == 1
        with pytest.raises(NotFoundError):
            world.appointments.get(999)

    def test_disponibilidad(self, world):
        self.schedule(world)
        slots = world.appointments.available_slots(world.doctor.id, date(2030, 1, 8))
        assert len(slots) == 19 and TUESDAY_10 not in slots
        assert world.appointments.available_slots(world.doctor.id, date(2030, 1, 12)) == []
        world.clock.advance_to(
            datetime(2030, 1, 8, 12, tzinfo=TZ)
        )  # ya pasaron las franjas de la mañana
        assert all(
            s.hour >= 12
            for s in world.appointments.available_slots(world.doctor.id, date(2030, 1, 8))
        )
