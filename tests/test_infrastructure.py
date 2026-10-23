from datetime import timedelta

import pytest

from app.domain.errors import AuthenticationError
from app.infrastructure.clock import SystemClock
from app.infrastructure.security import JwtTokenService, ScryptPasswordHasher
from app.settings import Settings
from tests.fakes import NOW, FixedClock

SECRET = "secreto-de-pruebas-con-al-menos-32-caracteres"


class TestPasswordHasher:
    def test_hash_y_verificacion(self):
        hasher = ScryptPasswordHasher()
        hashed = hasher.hash("clave-segura")
        assert hashed != "clave-segura" and hashed.startswith("scrypt$")
        assert hasher.verify("clave-segura", hashed)
        assert not hasher.verify("otra", hashed)

    def test_usa_sal_distinta_cada_vez(self):
        hasher = ScryptPasswordHasher()
        assert hasher.hash("igual") != hasher.hash("igual")

    def test_formato_corrupto_no_lanza_error(self):
        assert not ScryptPasswordHasher().verify("x", "no-es-un-hash")


class TestTokens:
    def service(self, clock=None, secret=SECRET):
        return JwtTokenService(secret, timedelta(minutes=5), clock or FixedClock(NOW))

    def test_emite_y_lee(self):
        service = self.service()
        assert service.read(service.issue(7)) == 7

    def test_rechaza_firma_distinta_y_basura(self):
        token = self.service().issue(7)
        with pytest.raises(AuthenticationError):
            self.service(secret="otro-secreto-distinto-de-32-caracteres!!").read(token)
        with pytest.raises(AuthenticationError):
            self.service().read("basura")

    def test_rechaza_token_vencido(self):
        clock = FixedClock(NOW)
        service = self.service(clock)
        token = service.issue(1)
        clock.advance_to(NOW + timedelta(minutes=6))
        with pytest.raises(AuthenticationError, match="expiró"):
            service.read(token)


class TestSettings:
    def test_exige_secreto(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            Settings.from_env()

    def test_rechaza_secreto_corto(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "corto")
        with pytest.raises(RuntimeError):
            Settings.from_env()

    def test_lee_el_entorno(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", SECRET)
        monkeypatch.setenv("CORS_ORIGINS", "http://a.co, http://b.co")
        settings = Settings.from_env()
        assert settings.cors_origins == ("http://a.co", "http://b.co")
        assert settings.clinic_timezone == "America/Bogota"


def test_el_reloj_del_sistema_tiene_zona_horaria():
    assert SystemClock().now().tzinfo is not None
