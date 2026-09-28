import logging
import logging.config
import os

_configured = False


def setup_logging(level: str | None = None) -> None:
    """
    Настраивает логирование ОДИН РАЗ для всего приложения. Вызывается в самом
    начале app.py, ДО импорта остальных модулей проекта - тогда
    logging.getLogger(__name__) в любом файле (routers/*, models/*, sources/*)
    унаследует эту конфигурацию автоматически через root-логгер.

    Два хендлера с РАЗНЫМ уровнем и форматом:
    - console: всё от LOG_LEVEL и выше, компактный формат - для чтения в терминале.
    - file: только WARNING и выше, МАКСИМАЛЬНО подробный формат (полный путь к файлу,
      PID/TID процесса, request_id) - ротируется по размеру, чтобы не разрастись
      бесконечно. Пишется в settings.LOG_DIR/settings.LOG_FILE_NAME и отдаётся
      целиком через отдельный эндпоинт /logs/download (см. routers/logs_router.py).

    _configured - защита от повторной инициализации (см. предыдущие комментарии) -
    без неё повторный dictConfig() на --reload или двойной импорт задвоил бы
    хендлеры и, следовательно, каждую строку лога.
    """
    global _configured
    if _configured:
        return
    _configured = True

    # импортируем здесь, а не в начале файла - core.config импортирует
    # dotenv/os и т.п.; держим logging_config без внешних зависимостей на
    # верхнем уровне, чтобы setup_logging() можно было звать максимально рано.
    from core.config import settings, LOG_FILE_PATH

    os.makedirs(
        settings.LOG_DIR, exist_ok=True
    )  # RotatingFileHandler не создаёт папку сам

    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": "core.request_context.RequestIdFilter"},
                # health-пробы k8s не пишем на INFO - см. HealthCheckFilter
                "skip_health": {"()": "core.request_context.HealthCheckFilter"},
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s | %(levelname)-8s | %(name)s | req=%(request_id)s | "
                        "%(filename)s:%(lineno)d:%(funcName)s | %(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "verbose_file": {
                    "format": (
                        "%(asctime)s | %(levelname)-8s | req=%(request_id)s | PID=%(process)d TID=%(thread)d | "
                        "%(name)s | %(pathname)s:%(lineno)d in %(funcName)s() | %(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id", "skip_health"],
                    "level": log_level,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "verbose_file",
                    "filters": ["request_id"],
                    "filename": LOG_FILE_PATH,
                    "maxBytes": settings.LOG_FILE_MAX_BYTES,
                    "backupCount": settings.LOG_FILE_BACKUP_COUNT,
                    "encoding": "utf-8",
                    "level": "WARNING",  # НЕЗАВИСИМО от LOG_LEVEL консоли - в файл только warning+
                },
            },
            "root": {"handlers": ["console", "file"], "level": log_level},
            "loggers": {
                # propagate=False + свои handlers - чтобы сообщения uvicorn тоже шли
                # через наш форматтер (и попадали в файл при warning+), а не дублировались
                # его собственным хендлером по умолчанию.
                "uvicorn": {
                    "level": log_level,
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": log_level,
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": log_level,
                    "handlers": ["console", "file"],
                    "propagate": False,
                },
            },
        }
    )
