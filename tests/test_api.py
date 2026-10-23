"""Pruebas de extremo a extremo: HTTP real (TestClient) sobre SQLite en memoria."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from tests.fakes import NOW, FixedClock

START = "2030-01-08T10:00:00-05:00"  # martes 10:00 en Bogotá


@pytest.fixture
def clock():
    return FixedClock(NOW)


@pytest.fixture
def client(clock):
    settings = Settings(
        jwt_secret="secreto-de-pruebas-con-al-menos-32-caracteres", database_url="sqlite://"
    )
    with TestClient(create_app(settings, clock)) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    creds = {"email": "recepcion@clinica.co", "password": "clave-segura-1"}
    assert client.post("/auth/register", json=creds).status_code == 201
    token = client.post("/auth/login", json=creds).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def ids(client, auth_headers):
    patient = client.post(
        "/patients",
        json={"full_name": "Ana Pérez", "document_id": "10001", "email": "ana@example.com"},
        headers=auth_headers,
    ).json()
    doctor = client.post(
        "/doctors",
        json={"full_name": "Dra. Rojas", "specialty": "Cardiología"},
        headers=auth_headers,
    ).json()
    return patient["id"], doctor["id"]


def book(client, headers, patient_id, doctor_id, start=START):
    return client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start": start,
            "reason": "Control",
        },
        headers=headers,
    )


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


class TestAuth:
    def test_las_rutas_protegidas_exigen_token(self, client):
        response = client.get("/patients")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    def test_token_invalido(self, client):
        assert client.get("/patients", headers={"Authorization": "Bearer abc"}).status_code == 401

    def test_registro_duplicado_y_login_incorrecto(self, client):
        creds = {"email": "a@b.co", "password": "clave-segura-1"}
        assert client.post("/auth/register", json=creds).status_code == 201
        assert client.post("/auth/register", json=creds).status_code == 409
        bad = client.post("/auth/login", json={**creds, "password": "incorrecta"})
        assert bad.status_code == 401

    def test_el_token_expira(self, client, clock, auth_headers):
        from datetime import timedelta

        clock.advance_to(NOW + timedelta(hours=2))
        assert client.get("/patients", headers=auth_headers).status_code == 401


class TestPatients:
    def test_crud_basico(self, client, auth_headers):
        body = {"full_name": "Ana Pérez", "document_id": "10001", "email": "ana@example.com"}
        created = client.post("/patients", json=body, headers=auth_headers)
        assert created.status_code == 201
        pid = created.json()["id"]
        assert client.post("/patients", json=body, headers=auth_headers).status_code == 409
        update = {"full_name": "Ana M. Pérez", "email": "ana@example.com", "phone": "3001112222"}
        assert (
            client.put(f"/patients/{pid}", json=update, headers=auth_headers).json()["phone"]
            == "3001112222"
        )
        assert client.get("/patients?q=m. p", headers=auth_headers).json()[0]["id"] == pid
        assert client.get("/patients/999", headers=auth_headers).status_code == 404

    def test_validacion_de_entrada(self, client, auth_headers):
        bad = {"full_name": "A", "document_id": "x", "email": "no-es-correo"}
        assert client.post("/patients", json=bad, headers=auth_headers).status_code == 422
        assert client.get("/patients?limit=0", headers=auth_headers).status_code == 422


class TestDoctors:
    def test_crear_listar_y_obtener(self, client, auth_headers, ids):
        _, doctor_id = ids
        assert (
            client.get("/doctors?specialty=cardiología", headers=auth_headers).json()[0]["id"]
            == doctor_id
        )
        assert client.get(f"/doctors/{doctor_id}", headers=auth_headers).status_code == 200
        assert client.get("/doctors/999", headers=auth_headers).status_code == 404


class TestAppointments:
    def test_flujo_completo(self, client, auth_headers, clock, ids):
        from datetime import timedelta

        patient_id, doctor_id = ids
        created = book(client, auth_headers, patient_id, doctor_id)
        assert created.status_code == 201
        appointment = created.json()
        assert appointment["status"] == "scheduled"
        assert appointment["end"].startswith("2030-01-08T15:30")

        availability = client.get(
            f"/doctors/{doctor_id}/availability?date=2030-01-08", headers=auth_headers
        )
        assert len(availability.json()["slots"]) == 19

        listed = client.get(
            f"/appointments?doctor_id={doctor_id}&date=2030-01-08", headers=auth_headers
        )
        assert [a["id"] for a in listed.json()] == [appointment["id"]]

        clock.advance_to(NOW + timedelta(days=1, hours=2))  # el token anterior ya expiró
        login = client.post(
            "/auth/login", json={"email": "recepcion@clinica.co", "password": "clave-segura-1"}
        )
        fresh = {"Authorization": f"Bearer {login.json()['access_token']}"}
        done = client.post(f"/appointments/{appointment['id']}/complete", headers=fresh)
        assert done.json()["status"] == "completed"

    def test_reglas_de_agenda(self, client, auth_headers, ids):
        patient_id, doctor_id = ids
        assert book(client, auth_headers, patient_id, doctor_id).status_code == 201
        assert book(client, auth_headers, patient_id, doctor_id).status_code == 409  # choque
        assert (
            book(
                client, auth_headers, patient_id, doctor_id, "2030-01-12T10:00:00-05:00"
            ).status_code
            == 422
        )
        assert book(client, auth_headers, 999, doctor_id).status_code == 404

    def test_cancelar(self, client, auth_headers, ids):
        patient_id, doctor_id = ids
        appointment_id = book(client, auth_headers, patient_id, doctor_id).json()["id"]
        cancelled = client.post(f"/appointments/{appointment_id}/cancel", headers=auth_headers)
        assert cancelled.json()["status"] == "cancelled"
        assert (
            client.post(f"/appointments/{appointment_id}/cancel", headers=auth_headers).status_code
            == 409
        )
        assert (
            client.get(f"/appointments/{appointment_id}", headers=auth_headers).status_code == 200
        )
        assert client.get("/appointments/999", headers=auth_headers).status_code == 404
