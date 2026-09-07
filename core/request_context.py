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
