"""
errors.py

Глобальный перехватчик НЕОБРАБОТАННЫХ исключений. Ловит любую ошибку из
ЛЮБОГО роутера/сервиса, которую вы явно не обернули в try/except с HTTPException -
то есть закрывает случаи, которые иначе улетели бы в FastAPI как "голый" 500
без единой строчки в логах.

logger.exception(...) (в отличие от logger.error(...)) автоматически прикладывает
ПОЛНЫЙ traceback - весь стек вызовов с именами файлов, номерами строк и функций
на каждом уровне, а не только там, где стоял вызов логгера. Это и есть основной
механизм "пройти по следам после ошибки": вы получаете не "что-то упало в
predict_dicom", а точный путь app.py -> ecg_signal_router.py:47:predict_dicom ->
model_service.py:63:predict -> ... вплоть до строки, где реально брошено исключение.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.request_context import get_request_id

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "Необработанное исключение: %s %s", request.method, request.url.path
        )
        request_id = get_request_id()
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "detail": str(exc),
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )
