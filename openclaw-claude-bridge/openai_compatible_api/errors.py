"""Standardized error response format for OpenAI-compatible API."""
from typing import Optional


class ErrorResponse:
    """Standardized error response (OpenAI-compatible format)."""

    def __init__(
        self,
        message: str,
        error_type: str,
        code: str,
        status: int,
        param: Optional[str] = None
    ):
        self.message = message
        self.type = error_type
        self.code = code  # Machine-readable string slug
        self.status = status  # HTTP status code
        self.param = param

    def to_dict(self) -> dict:
        return {
            "error": {
                "message": self.message,
                "type": self.type,
                "code": self.code,
                "param": self.param,
                "status": self.status
            }
        }


# Pre-defined errors (OpenAI standard format)
ERROR_MISSING_API_KEY = ErrorResponse(
    message="Missing API Key",
    error_type="authentication_error",
    code="missing_api_key",
    status=401
)

ERROR_INVALID_API_KEY = ErrorResponse(
    message="Invalid API Key",
    error_type="authentication_error",
    code="invalid_api_key",
    status=401
)

ERROR_MISSING_FIELD = lambda field: ErrorResponse(
    message=f"Missing required field: {field}",
    error_type="invalid_request_error",
    code="missing_field",
    status=400,
    param=field
)

ERROR_MODEL_NOT_FOUND = lambda model_id: ErrorResponse(
    message=f"Model not found: {model_id}",
    error_type="invalid_request_error",
    code="model_not_found",
    status=400,
    param="model"
)

ERROR_RATE_LIMIT = ErrorResponse(
    message="Rate limit exceeded",
    error_type="rate_limit_error",
    code="rate_limit_exceeded",
    status=429
)

ERROR_INTERNAL = ErrorResponse(
    message="Internal server error",
    error_type="internal_error",
    code="internal_error",
    status=500
)

ERROR_TIMEOUT = ErrorResponse(
    message="Request timeout",
    error_type="timeout_error",
    code="timeout",
    status=504
)

ERROR_NOT_FOUND = ErrorResponse(
    message="Session not found",
    error_type="not_found_error",
    code="not_found",
    status=404
)

ERROR_CONFLICT = ErrorResponse(
    message="Request conflict: another request is in-flight",
    error_type="conflict_error",
    code="request_conflict",
    status=409
)
