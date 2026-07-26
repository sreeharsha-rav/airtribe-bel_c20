import contextvars
import json
import logging
import time
import uuid


request_id_var = contextvars.ContextVar("request_id", default="-")
logger = logging.getLogger("pulse_notify.request")

_RESERVED_ATTRS = frozenset(
    logging.LogRecord(
        name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None,
    ).__dict__.keys()
) | {"message", "asctime"}


class RequestIDLogFilter(logging.Filter):
    """Injects the current request's correlation id into every log record."""

    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class JSONFormatter(logging.Formatter):
    """Renders each log record as a single-line JSON object.

    Standard fields (timestamp, level, logger, message, request_id, ...) are
    always present; anything passed via `extra={...}` is merged in as-is so
    call sites can attach arbitrary searchable fields without schema changes.
    """

    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": getattr(record, "request_id", "-"),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class RequestLoggingMiddleware:
    """Logs one structured line per request with timing, actor, and outcome.

    Placed first in MIDDLEWARE so the measured duration covers the full
    request/response cycle.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        status_code = None
        start_time = time.monotonic()
        try:
            response = self.get_response(request)
            status_code = response.status_code
            response["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception(
                f"Unhandled exception: {request.method} {request.path}",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "user": self._get_user(request),
                },
            )
            raise
        finally:
            elapsed = self._elapsed_time_ms(start_time)
            logger.info(
                f"{request.method} {request.path} {status_code or 'ERR'} {elapsed:.2f}ms",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status_code": status_code,
                    "duration_ms": elapsed,
                    "user": self._get_user(request),
                },
            )
            request_id_var.set("-")

    @staticmethod
    def _elapsed_time_ms(start_time):
        return round((time.monotonic() - start_time) * 1000, 2)

    @staticmethod
    def _get_user(request):
        user = getattr(request, "user", None)
        if user is None:
            return "-"
        return str(user.pk) if getattr(user, "is_authenticated", False) else "anonymous"
