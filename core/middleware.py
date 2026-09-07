"""
middleware.py

Проставляет request_id на весь жизненный цикл запроса (contextvar), берёт его
из заголовка X-Request-ID если клиент уже прислал свой (удобно для сквозной
трассировки через несколько сервисов), иначе генерирует новый. Также
возвращает его в ответе тем же заголовком - можно сопоставить конкретный
ответ у клиента с конкретными строчками в серверных логах.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.request_context import new_request_id, set_request_id

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", new_request_id())
        set_request_id(request_id)

        start = time.monotonic()
        logger.info("--> %s %s", request.method, request.url.path)
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        logger.info(
            "<-- %s %s %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
