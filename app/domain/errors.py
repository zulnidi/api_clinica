"""Errores de dominio. La capa HTTP los traduce a códigos de estado."""


class DomainError(Exception):
    """Base de todos los errores de negocio."""


class ValidationError(DomainError):
    """Datos que incumplen una regla de negocio (HTTP 422)."""


class NotFoundError(DomainError):
    """El recurso no existe (HTTP 404)."""


class ConflictError(DomainError):
    """La operación choca con el estado actual (HTTP 409)."""


class AuthenticationError(DomainError):
    """Credenciales o token inválidos (HTTP 401)."""
