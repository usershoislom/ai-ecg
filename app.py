import time
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging_config import setup_logging

setup_logging()

from core.middleware import RequestIdMiddleware
from core.errors import register_exception_handlers

from models.ecg_signal.model_service import ModelService
from models.ecg_signal_raw150.model_service_raw150 import RawECGFounderService
from routers import ecg_signal_router
from routers import logs_router
from routers import annotation_router
from core.config import settings

from db.database import create_all_tables, AsyncSessionLocal
from db.seed import seed_default_classes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск приложения - загрузка модели...")
    start = time.time()
    ModelService.get_instance()  # прогреваем singleton один раз при старте
    RawECGFounderService.get_instance()
    logger.info(f"Модель загружена за {time.time() - start:.2f} секунд")

    await create_all_tables()
    async with AsyncSessionLocal() as db:
        await seed_default_classes(db)

    yield
    logger.info("Остановка приложения")


app = FastAPI(
    title="ECG AI Service", version="2.0.0", lifespan=lifespan, redirect_slashes=True
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIdMiddleware)
register_exception_handlers(app)

app.include_router(ecg_signal_router.router, prefix="/api", tags=["ecg-signal"])
app.include_router(logs_router.router, prefix="/api", tags=["logs"])
app.include_router(annotation_router.router, prefix="/api", tags=["annotation"])


@app.get("/api/health", response_model=dict)
@app.get("/api/health/", response_model=dict, include_in_schema=False)
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=settings.PORT,
    )
