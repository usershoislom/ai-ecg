"""
logs_router.py

Отдаёт файл логов (WARNING+, см. core/logging_config.py) целиком для скачивания.

ВАЖНО (безопасность/PHI): в лог попадают, среди прочего, имена загруженных
DICOM-файлов (см. logger.info("...: %s", file.filename) в ecg_signal_router.py) -
если в вашем контуре имена файлов могут содержать идентифицирующие пациента
данные, этот эндпоинт фактически отдаёт файл с потенциальным PHI кому угодно,
кто до него достучится. На проде этот роут обязательно должен быть закрыт
авторизацией (см. пример с APIKey ниже) или доступен только из внутренней сети/VPN -
без явного намерения пользователя оставляю его БЕЗ авторизации по умолчанию
(как задача была сформулирована), но не подключайте его как есть на прод.
"""

import logging
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.config import settings, LOG_FILE_PATH

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/logs/download")
def download_logs():
    if not os.path.exists(LOG_FILE_PATH):
        raise HTTPException(
            status_code=404,
            detail="Файл логов ещё не создан - не было ни одного warning/error",
        )

    return FileResponse(
        path=LOG_FILE_PATH,
        filename=settings.LOG_FILE_NAME,
        media_type="text/plain",
    )
