# ECG AI Service — доступ для мониторинга

## Адреса

| Среда | Base URL API | Swagger UI | ReDoc | OpenAPI JSON | Health |
|---|---|---|---|---|---|
| dev | `https://api-ecg-ai.med-uic.uz/api` | `https://api-ecg-ai.med-uic.uz/docs` | `https://api-ecg-ai.med-uic.uz/redoc` | `https://api-ecg-ai.med-uic.uz/openapi.json` | `https://api-ecg-ai.med-uic.uz/api/health` |
| prod | `https://api-ecg-ai.ssv.uz/api` | `https://api-ecg-ai.ssv.uz/docs` | `https://api-ecg-ai.ssv.uz/redoc` | `https://api-ecg-ai.ssv.uz/openapi.json` | `https://api-ecg-ai.ssv.uz/api/health` |

Health-ответ: `200 {"status":"ok"}`. Отвечает только после того, как обе модели загружены и
БД доступна (lifespan), поэтому годится и как readiness.

## Аутентификация

**На текущий момент аутентификации нет** — все эндпоинты, включая Swagger и
`GET /api/logs/download/`, открыты для любого, кто имеет сетевой доступ к URL.
Доступ ограничен только сетевым периметром (ingress кластера).

Что нужно для доступа к Swagger: открыть ссылку из таблицы в браузере из сети, где доступен
ingress. Все запросы можно выполнять прямо из Swagger («Try it out»).

## Что смотреть при мониторинге

| Что | Как | Норма |
|---|---|---|
| Живость | `GET /api/health` | 200, < 50 мс |
| Инференс | `POST /api/predict/dicom/` с тестовым файлом из `ecg_output/` (см. `docs/TESTING.md`) | 200, < 2 с на CPU, `positive_classes: ["NORM"]` |
| PACS | `POST /api/predict/pacs/` с реальными UID | 200; `502` = проблема с PACS, не с сервисом |
| БД | `GET /api/annotation/classes/` | 200, ≥ 6 суперклассов; `500` = проблема с Postgres |
| Ошибки | `GET /api/logs/download/` или Graylog, фильтр `level:WARNING` и выше, pod `ai-ecg-backend-*` | нет новых ERROR |
| Трассировка запроса | заголовок `X-Request-ID` из ответа → поиск `req=<id>` в Graylog | все строки запроса |

## Сервисные учётные данные, которые использует сам бэкенд

| Ресурс | Где хранится | Примечание |
|---|---|---|
| PostgreSQL `pgcloud.tech-uic.uz:5433/ai_ecg` | `DATABASE_URL` в секретах k8s (`.env` локально, в git не входит) | пул 3+5 соединений |
| PACS dcm4chee `195.158.10.39:8080` | `PACS_BASE_URL`, без auth | WADO-RS |
| Harbor, GitOps-репозиторий | переменные GitLab CI (`HARBOR_*`, `GITOPS_TOKEN_MOH`) | только для CI |
