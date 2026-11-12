import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("app")


class AppError(Exception):
    status_code = 500

    def __init__(self, detail: str, code: str | None = None):
        self.detail, self.code = detail, code


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class BadInput(AppError):
    status_code = 422


def register_error_handlers(app):
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse(
            {"detail": exc.detail, "code": exc.code}, status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        msg = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()
        )
        return JSONResponse(
            {"detail": msg or "Invalid input.", "code": "invalid_input"}, status_code=422
        )

    @app.exception_handler(Exception)
    async def fallback(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(
            {"detail": "Something went wrong on the server.", "code": "server_error"},
            status_code=500,
        )
