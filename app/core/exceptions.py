"""
Custom Exception Classes
========================
Equivalent to Laravel's custom Exception classes + Handler.php mapping.

All exceptions are registered as global handlers in app/main.py.
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """
    Base application exception.
    Equivalent to Laravel's base Exception that maps to HTTP responses.
    """

    status_code: int = 500
    message: str = "An unexpected error occurred."
    errors: dict[str, Any] | None = None

    def __init__(
        self,
        message: str | None = None,
        errors: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.errors = errors
        super().__init__(self.message)


class NotFoundException(AppException):
    """
    Resource not found.
    Equivalent to Laravel's ModelNotFoundException → 404.
    """
    status_code = 404
    message = "Resource not found."


class UnauthorizedException(AppException):
    """
    Unauthenticated request.
    Equivalent to Laravel's AuthenticationException → 401.
    """
    status_code = 401
    message = "Unauthenticated. Please provide a valid token."


class ForbiddenException(AppException):
    """
    Authenticated but not authorized.
    Equivalent to Laravel's AuthorizationException → 403.
    """
    status_code = 403
    message = "You do not have permission to perform this action."


class ValidationException(AppException):
    """
    Request validation failed.
    Equivalent to Laravel's ValidationException → 422.
    """
    status_code = 422
    message = "The given data was invalid."

    def __init__(self, errors: dict[str, Any]) -> None:
        super().__init__(message=self.message, errors=errors)


class ConflictException(AppException):
    """
    Resource already exists / state conflict.
    Equivalent to returning 409 from a Laravel controller.
    """
    status_code = 409
    message = "A conflict occurred with the current state of the resource."


class UnprocessableException(AppException):
    """Business logic rule violation — 422."""
    status_code = 422
    message = "Unable to process this request."


class ServiceUnavailableException(AppException):
    """Downstream service (AI, storage, etc.) is unavailable — 503."""
    status_code = 503
    message = "A required service is currently unavailable. Please try again later."
