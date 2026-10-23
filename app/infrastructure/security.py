import hashlib
import hmac
import os
from datetime import timedelta

import jwt

from app.application.ports import Clock
from app.domain.errors import AuthenticationError


class ScryptPasswordHasher:
    """Hash con scrypt (biblioteca estándar): sal aleatoria y comparación en tiempo constante."""

    N, R, P = 2**14, 8, 1

    def hash(self, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=self.N, r=self.R, p=self.P)
        return f"scrypt${salt.hex()}${digest.hex()}"

    def verify(self, password: str, hashed: str) -> bool:
        try:
            _, salt_hex, digest_hex = hashed.split("$")
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt_hex), n=self.N, r=self.R, p=self.P
            )
        except ValueError:
            return False
        return hmac.compare_digest(actual, expected)


class JwtTokenService:
    def __init__(self, secret: str, expires: timedelta, clock: Clock):
        self._secret, self._expires, self._clock = secret, expires, clock

    def issue(self, user_id: int) -> str:
        now = self._clock.now()
        payload = {"sub": str(user_id), "iat": now, "exp": now + self._expires}
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def read(self, token: str) -> int:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                options={
                    "verify_exp": False,
                    "verify_iat": False,
                },  # el tiempo se valida con nuestro Clock
            )
            if payload["exp"] <= self._clock.now().timestamp():
                raise AuthenticationError("El token expiró.")
            return int(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise AuthenticationError("Token inválido.") from exc
