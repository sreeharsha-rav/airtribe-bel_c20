import contextvars
import json
import logging
import time
import uuid

request_id_var = contextvars.ContextVar("request_id", default="-")

logger = logging.getLogger("clear_ledger.request")

_RESERVED_ATTRS = frozenset(logging.LogRecord(
    name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None,
).__dict__.keys()) | {"message", "asctime"}


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

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_ATTRS and key not in payload
        }
        payload.update(extras)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class RequestLoggingMiddleware:
    """Logs one structured line per request with timing, actor, and outcome.

    Placed first in MIDDLEWARE so the measured duration covers the full
    stack, and the request id is available to every log statement emitted
    while handling the request (via the `request_id` contextvar/filter).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        start = time.monotonic()

        try:
            response = self.get_response(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra=self._context(request, duration_ms=self._elapsed_ms(start)),
            )
            raise
        else:
            response["X-Request-ID"] = request_id
            logger.info(
                "request_completed",
                extra=self._context(
                    request,
                    duration_ms=self._elapsed_ms(start),
                    status_code=response.status_code,
                    response_size=response.get("Content-Length"),
                ),
            )
            return response
        finally:
            request_id_var.reset(token)

    @staticmethod
    def _elapsed_ms(start):
        return round((time.monotonic() - start) * 1000, 2)

    @classmethod
    def _context(cls, request, **extra):
        context = {
            "http_method": request.method,
            "path": request.path,
            "query_string": request.META.get("QUERY_STRING", ""),
            "user": cls._user_label(request),
            "ip": cls._client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        }
        context.update(extra)
        return context

    @staticmethod
    def _user_label(request):
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return "anonymous"
        return user.get_username()

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")