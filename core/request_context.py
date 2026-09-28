"""
request_context.py

Даёт каждому HTTP-запросу свой request_id, доступный ЛЮБОМУ логгеру в проекте
(в любом router/service/source файле), без явной передачи параметром через
всю цепочку вызовов - используется contextvars, который FastAPI/Starlette/anyio
корректно копируют в threadpool для sync-эндпоинтов и в дочерние async-таски
в рамках одного запроса.

Смысл: если в логах несколько запросов идут вперемешку (параллельные клиенты),
можно отфильтровать/сгруппировать строки одного запроса по request_id и
восстановить полную цепочку "какие функции звал этот конкретный запрос
и где именно упал" - это и есть тот "след", который вы просили.
"""

import contextvars
import logging
import uuid

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def new_request_id() -> str:
    return uuid.uuid4().hex[:8]


def set_request_id(value: str) -> None:
    _request_id_ctx.set(value)


def get_request_id() -> str:
    return _request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    """
    Подставляет %(request_id)s в КАЖДУЮ запись лога, откуда бы она ни пришла.
    Обязателен, если формат в logging_config.py ссылается на %(request_id)s -
    без фильтра обычный LogRecord этого атрибута не имеет и упадёт KeyError
    при форматировании.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class HealthCheckFilter(logging.Filter):
    """
    Отсекает записи о health-пробах (k8s liveness/readiness, Docker HEALTHCHECK)
    из консольного вывода: они идут каждые несколько секунд и в Graylog
    полностью забивают реальные запросы. Смотрим на уже отформатированное
    сообщение, т.к. путь попадает в лог по-разному: у uvicorn.access - в args
    (форматная строка '%s - "%s %s HTTP/%s" %d'), у core.middleware - как
    отдельный аргумент. Ошибки (WARNING+) не трогаем - если проба падает,
    это нужно видеть.
    """

    HEALTH_PATHS = ("/api/health",)

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        try:
            message = record.getMessage()
        except Exception:
            return True
        return not any(path in message for path in self.HEALTH_PATHS)
