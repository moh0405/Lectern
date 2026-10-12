"""One error shape for every failure: {"error": {"code", "message", "details"?}}."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("ai-study-mentor.api")

_CODES = {
    400: "bad_request",
    401: "unauthorized",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    502: "llm_error",
    503: "unavailable",
}


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(HTTPException):
    """HTTPException with an explicit machine-readable code."""

    def __init__(self, status_code: int, message: str, code: Optional[str] = None, details: Any = None,
                 headers: Optional[dict] = None):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code or _CODES.get(status_code, "error")
        self.details = details


def _response(status: int, code: str, message: str, details: Any = None, headers: Optional[dict] = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True), headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException):
        code = getattr(exc, "code", None) or _CODES.get(exc.status_code, "error")
        return _response(exc.status_code, code, str(exc.detail), getattr(exc, "details", None), getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
        return _response(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return _response(500, "internal_error", "Internal server error")


# Declared on routes so the OpenAPI schema (and the generated TS client) knows the error shape.
ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
