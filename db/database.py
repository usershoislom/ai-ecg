"""
database.py

Async-подключение к PostgreSQL через SQLAlchemy 2.x. Первая persistence-фича
в проекте.
Заложено так, чтобы этой же БД потом воспользоваться и под task_id/историю
предсказаний, не переделывая инфраструктуру заново.
"""

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=180,  # переподключаться проактивно раз в 3 мин - пока это
    # МЫ решаем закрыть простаивающее соединение, а не
    # файрвол/NAT/managed-БД молча делают это за нас
    # (см. WinError 121 в реальном инциденте - соединение
    # протухло по сети раньше, чем мы успели это заметить)
    pool_size=3,  # 5 врачей максимум - большой пул не нужен, экономим
    max_overflow=5,  # квоту подключений на dev-инстансе pgcloud
    connect_args={
        "timeout": 10,  # секунд на установление TCP/SSL-соединения -
        # без этого Windows держит его до ~20-30+ сек
        # (см. WinError 121), запрос к API зависает надолго
        # вместо быстрого понятного фейла
        "command_timeout": 10,  # секунд на выполнение отдельного запроса
    },
)
AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def create_all_tables():
    """
    Быстрый старт БЕЗ Alembic - create_all по моделям. Для прототипа/MVP этого
    достаточно; когда схема стабилизируется и понадобятся управляемые миграции
    (rename колонки, backfill и т.п.) - заменить на `alembic upgrade head`
    в lifespan вместо этого вызова.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
