"""
check_db_connectivity.py

Отдельный диагностический скрипт - НЕ часть приложения. Проверяет стабильность
сети до БД независимо от FastAPI/пула соединений, чтобы понять: разовый ли это
сбой (WinError 121) или системная проблема (файрвол/NAT рвёт простаивающие
соединения через N минут).

Запуск:
    uv run check_db_connectivity.py

Оставьте работать на 15-20 минут (дольше типичного NAT-таймаута простоя,
обычно 5-15 минут) и посмотрите на вывод: если фейлы происходят регулярно
через примерно одинаковые интервалы - это файрвол/NAT, стоит показать
результат вашей сетевой команде/devops. Если фейлы редкие и нерегулярные -
скорее просто нестабильный канал, тогда retry-логики в самом приложении
достаточно.
"""

import asyncio
import time

import asyncpg

from db.database import DATABASE_URL

# asyncpg сам не понимает +asyncpg в схеме (это SQLAlchemy-специфичный синтаксис) -
# убираем для прямого подключения через asyncpg.connect()
RAW_DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

CHECK_INTERVAL_SEC = 30


async def probe():
    start = time.monotonic()
    try:
        conn = await asyncpg.connect(RAW_DSN, timeout=10)
        elapsed = time.monotonic() - start
        await conn.execute("SELECT 1")
        await conn.close()
        print(f"[{time.strftime('%H:%M:%S')}] OK  (подключение заняло {elapsed:.2f}с)")
        return True
    except Exception as e:
        elapsed = time.monotonic() - start
        print(
            f"[{time.strftime('%H:%M:%S')}] FAIL после {elapsed:.2f}с: {type(e).__name__}: {e}"
        )
        return False


async def main():
    print(
        f"Проверяю подключение к БД каждые {CHECK_INTERVAL_SEC}с. Ctrl+C для остановки."
    )
    print(f"DSN (без пароля): {RAW_DSN.split('@')[-1]}")
    print()
    fails = 0
    total = 0
    while True:
        ok = await probe()
        total += 1
        if not ok:
            fails += 1
        if total % 10 == 0:
            print(f"  --- итого: {fails}/{total} неудачных попыток ---")
        await asyncio.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановлено.")
