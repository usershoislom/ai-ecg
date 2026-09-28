# ECG AI Service — архитектура

Сервис автоматической интерпретации 12-канальной ЭКГ покоя. Принимает ЭКГ в виде
DICOM Waveform (файлом или напрямую из PACS), возвращает вероятности диагностических
классов, объяснение решения (теплокарта по отведениям) и клинические метаданные аппарата.
Отдельный модуль — аннотирование исследований врачами для сбора разметки.

Репозиторий бэкенда: `git.uzinfocom.uz/moh/apdai/ai/ai-ecg/beckend`.

## 1. Общая схема

```
 ┌───────────────┐   HTTPS/JSON, multipart      ┌──────────────────────────────────┐
 │  Frontend     │ ───────────────────────────► │  Backend  (FastAPI, Python 3.12) │
 │  (веб-клиент  │ ◄─────────────────────────── │  1 pod, 1 uvicorn worker         │
 │   врача)      │   JSON / PNG                  │                                  │
 └───────────────┘                               │  ┌────────────┐  ┌────────────┐ │
                                                 │  │ ECGFounder │  │ ECGFounder │ │
                                                 │  │ fine-tuned │  │ raw 150 cl.│ │
                                                 │  │ 5 классов  │  │            │ │
                                                 │  └────────────┘  └────────────┘ │
                                                 └───────┬─────────────┬───────────┘
                                                         │ WADO-RS      │ asyncpg
                                                         ▼              ▼
                                            ┌──────────────────┐  ┌──────────────────┐
                                            │ PACS dcm4chee    │  │ PostgreSQL       │
                                            │ 195.158.10.39    │  │ pgcloud.tech-    │
                                            │ :8080            │  │ uic.uz:5433/ai_ecg│
                                            └──────────────────┘  └──────────────────┘

 stdout контейнера ──► Graylog          GitLab CI ──► Harbor ──► GitOps repo ──► Kubernetes
```

Стенды:

| Среда | Ветка | API | Сервер |
|---|---|---|---|
| dev | `dev` | `https://api-ecg-ai.med-uic.uz/api` | 10.10.17.20 |
| prod | `main` | `https://api-ecg-ai.ssv.uz/api` | 10.10.17.110 |

## 2. Frontend

Бэкенд-репозиторий не содержит фронта; ниже — контракт, которым фронт пользуется
(полное описание: `api_docs.md`). Стек, репозиторий и хостинг фронта заполняет
фронтенд-разработчик.

Сценарий врача:

1. Открывает исследование (UID приходят из PACS/МИС).
2. `POST /predict/pacs/` — получает 5 классов с вероятностями и флагом `positive`;
   параллельно `POST /metadata/pacs/` — демография, измерения аппарата (ЧСС, PR, QRS, QT,
   вольтажные критерии), текстовое заключение аппарата.
3. Для положительных классов — `POST /explain/pacs/image/?class_name=X` (готовый PNG)
   или `POST /explain/pacs/` (числовые карты для собственной отрисовки).
4. При необходимости `POST /predict/pacs/raw150/` — top-10 из 150 классов исходной модели.
5. Аннотирует: `GET /annotation/classes/?lang=uz` → выбирает суперклассы и подклассы →
   `POST /annotation/`. Может добавить свой подкласс `POST /annotation/classes/`.

Локализация — параметр `lang=ru|uz` для аннотаций; в ответах предсказаний названия
приходят сразу на обоих языках (`name: {ru, uz}`).

## 3. Backend

### 3.1 Стек

| Компонент | Версия | Назначение |
|---|---|---|
| Python | 3.12 | |
| FastAPI / Starlette | 0.141 | HTTP, OpenAPI/Swagger |
| uvicorn | 0.52 | ASGI-сервер, 1 worker |
| PyTorch | 2.13 (CPU-сборка в контейнере) | инференс Net1D |
| pydicom | 3.0 | разбор DICOM Waveform |
| scipy / numpy | 1.18 / 2.5 | фильтрация, ресемплинг |
| matplotlib | 3.11 | рендер PNG-объяснений |
| SQLAlchemy 2 (async) + asyncpg | 2.0 / 0.31 | PostgreSQL |
| requests | 2.34 | WADO-RS к PACS |
| wfdb | 4.3 | чтение PTB-XL для внутренних проверок |
| uv | — | менеджер зависимостей (`pyproject.toml`, `uv.lock`) |

### 3.2 Структура кода

```
app.py                      точка входа: lifespan (прогрев моделей, create_all, seed БД), CORS, роутеры
core/
  config.py                 Settings из переменных окружения / .env
  logging_config.py         консоль (INFO, → Graylog) + файл logs/app.log (WARNING+, ротация)
  middleware.py             X-Request-ID на запрос, тайминг
  request_context.py        contextvar request_id, фильтры логов (request_id, health-пробы)
  errors.py                 глобальный обработчик 500 с traceback в лог
  schemas.py                Pydantic-схемы ответов predict/metadata
  annotation_schemas.py     Pydantic-схемы аннотаций
  diagnostic_labels.py      статические переводы ru/uz: 5 суперклассов + 150 классов претрейна
  codegen.py                генерация машинного code для кастомных классов (транслитерация)
models/
  ecg_signal/net1d.py       архитектура Net1D (ECGFounder)
  ecg_signal/model_service.py         singleton: дообученная модель, 5 классов + пороги
  ecg_signal/preprocessing.py         единый препроцессинг сигнала
  ecg_signal/explainability.py        Grad-CAM++, Integrated Gradients
  ecg_signal/explain_rendering.py     PNG 12 отведений с теплокартой
  ecg_signal_raw150/model_service_raw150.py   singleton: исходная модель, 150 классов
sources/
  dicom_signal.py           DICOM Waveform → сигнал в мВ, имена отведений, fs
  dicom_metadata.py         DICOM → демография, измерения, текстовые заключения
  pacs_client.py            WADO-RS GET instance, разбор multipart
  wfdb_service.py           локальные WFDB-записи (PTB-XL)
routers/
  ecg_signal_router.py      /predict, /metadata, /explain
  annotation_router.py      /annotation/*
  logs_router.py            /logs/download
db/
  database.py               async engine, пул, get_db
  models.py                 annotation_classes, annotations, annotation_class_links
  seed.py                   дефолтные 6 суперклассов + 149 подклассов (идемпотентно)
train_utils.py              общий модуль с ноутбуком файнтюна (фильтры, Dataset, метрики, пороги)
weights/                    веса моделей (в git, ~490 МБ)
```

### 3.3 Жизненный цикл запроса

1. `RequestIdMiddleware` берёт `X-Request-ID` из заголовка или генерирует 8 hex,
   кладёт в contextvar, логирует `--> METHOD path`, после ответа `<-- ... status (ms)`
   и возвращает `X-Request-ID` в ответе. Все строки лога внутри запроса содержат `req=<id>` —
   по нему в Graylog собирается вся цепочка одного запроса.
2. Роутер: извлечение сигнала → препроцессинг → инференс → сборка ответа.
   Ожидаемые ошибки входа → `400` (`ValueError`), PACS → `502`, WFDB не найден → `404`,
   остальное → `500` с traceback в логе через `logger.exception`.
3. Необработанные исключения ловит `errors.py`: `500` + `request_id` в теле.

Эндпоинты с загрузкой файла — `async def` (чтение multipart), с PACS — `def`
(блокирующий `requests` уходит в threadpool Starlette).

### 3.4 Эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/health` | liveness/readiness (k8s), `{"status":"ok"}` |
| POST | `/api/predict/dicom/` | 5 классов с порогами по загруженному DICOM |
| POST | `/api/predict/pacs/` | то же, DICOM по UID из PACS |
| POST | `/api/predict/wfdb/` | то же по WFDB-записи внутри `WFDB_ROOT` (внутренний) |
| POST | `/api/predict/dicom/raw150/`, `/api/predict/pacs/raw150/` | 150 классов исходной модели, top-K |
| POST | `/api/metadata/dicom/`, `/api/metadata/pacs/` | метаданные DICOM без модели |
| POST | `/api/explain/dicom/`, `/api/explain/pacs/` | Grad-CAM++ + IG для каждого положительного класса (JSON) |
| POST | `/api/explain/dicom/image/`, `/api/explain/pacs/image/` | то же для одного класса, PNG |
| GET | `/api/logs/download/` | файл логов WARNING+ |
| GET/POST/DELETE | `/api/annotation/classes/...` | справочник классов, кастомные классы, soft-delete, activate |
| GET/POST/PUT/DELETE | `/api/annotation/...` | аннотации: по study, по id, список с пагинацией |

Swagger: `/docs`, ReDoc: `/redoc`, схема: `/openapi.json`.

## 4. ML-часть

### 4.1 Модели

Обе модели — одна архитектура **Net1D** (ECGFounder, Shenda Hong et al.): 1D-ResNet-подобная
сеть, `first_conv` (12 → 64 каналов) → 7 стейджей `BasicStage` с фильтрами
`[64, 160, 160, 400, 400, 1024, 1024]` и блоками `[2, 2, 2, 3, 3, 4, 4]`, kernel 16, stride 2,
grouped conv (ширина группы 16), без BatchNorm/Dropout → global average pooling по времени →
`Linear(1024, n_classes)`. Вход `[batch, 12, 5000]`, выход — логиты; multi-label, поэтому
на выходе `sigmoid` по каждому классу независимо.

| | Дообученная (основная) | Исходная (raw150) |
|---|---|---|
| Файл | `weights/ecg_signal/best.pth` (123 МБ) | `weights/ecg_founder_150/12_lead_ECGFounder.pth` (370 МБ) |
| Классы | 5 суперклассов PTB-XL: NORM, MI, CD, HYP, STTC | 150 диагнозов претрейна ECGFounder (`tasks.txt`) |
| Обучение | файнтюн ECGFounder на PTB-XL (ноутбук `ecg_finetune_v2.ipynb`, вне репозитория), `train_utils.py` общий | открытые претрейн-веса авторов ECGFounder, без изменений |
| Пороги | per-class из `weights/ecg_signal/thresholds.json` (подбор по чувствительности/специфичности, `export_thresholds.py`); **файл сейчас не выложен → 0.5** | нет, только вероятности; `TOP_K_150=10` |
| Загрузка | `strict=True`, весь state_dict | `strict=True` |
| Устройство | `DEVICE` из env, фолбэк на CPU если CUDA недоступна; на стенде — CPU | то же |

Обе модели — singleton, грузятся один раз при старте (lifespan), ~1 с на CPU.

### 4.2 Пайплайн предсказания

```
DICOM bytes
  │ sources/dicom_signal.py
  ├─ WaveformSequence[0]: NumberOfWaveformChannels, NumberOfWaveformSamples, SamplingFrequency
  ├─ WaveformData → int16/uint16/… по WaveformBitsAllocated/SampleInterpretation → [N, C]
  ├─ на канал: имя отведения из ChannelSourceSequence.CodeMeaning ("Lead I" → "I"),
  │            physical_mV = raw * ChannelSensitivity * CorrectionFactor * unit_factor + ChannelBaseline
  │            (единицы из ChannelSensitivityUnitsSequence; если нет — считаем µV с WARNING)
  ▼ ExtractedSignal(signal [C, N] мВ, lead_names, fs)
  │ preprocessing.reorder_leads
  ├─ перестановка в канонический порядок I, II, III, aVR, aVL, aVF, V1..V6; нет отведения → 400
  ▼
  │ preprocessing.preprocess_raw_signal   (те же функции, что на трейне — train_utils)
  ├─ NaN → 0
  ├─ crop/pad до 10 с на родной fs (центрированно, паддинг нулями)
  ├─ filter_ecg: HP 0.5 Гц → notch 50 Гц (Q=30) → LP 40 Гц (Butterworth 2-го порядка, zero-phase)
  ├─ линейный ресемплинг до 5000 отсчётов (= 500 Гц × 10 с)
  ├─ z-score по всему массиву [12, 5000] (одно среднее/σ на запись)
  ▼ float32 [12, 5000]
  │ ModelService.predict
  ├─ forward → sigmoid → probability; positive = probability >= threshold[class]
  ▼ PredictionResponse: predictions[5] {label, name{ru,uz}, probability, threshold, positive},
                        positive_classes, source{filename|UIDs, fs}
```

Требования к входу: ровно 12 стандартных отведений, любая fs, любая длительность
(обрезается/дополняется до 10 с), только DICOM Waveform (не изображение).

### 4.3 Объяснимость

Только для 5-классовой модели и только для положительных классов (иначе непонятно, что объяснять).
На каждый класс — отдельный forward+backward по логиту класса:

- **Grad-CAM++** на выходе `stage_list[-2]` (1024 канала, 1 отсчёт CAM ≈ 250 мс) → одна карта
  на все отведения (первая свёртка смешивает каналы), интерполируется до 5000;
- **Integrated Gradients** на входе `[12, 5000]` (50 шагов, baseline — нули) → карта по отведениям;
- **combined** = Grad-CAM++ × |IG| нормализованные → `[12, 5000]` в [0, 1].

PNG: сигнал после того же crop/filter/resample, но **без z-score** (в мВ), сетка 6×2, теплокарта
`YlOrRd` с контрастной растяжкой по каждому отведению (только визуал, числа в JSON не меняются).

### 4.4 Переводы

`core/diagnostic_labels.py` — статический словарь в коде, намеренно не из БД: `/predict`
остаётся stateless и не зависит от доступности Postgres и от правок врачей в справочнике
аннотаций. Для 150 классов претрейна перевод ищется по английскому имени из `tasks.txt`;
неизвестное имя возвращается как есть.

## 5. Источники данных

| Источник | Как | Где используется |
|---|---|---|
| Загрузка файла | multipart `file` | `/predict/dicom/`, `/metadata/dicom/`, `/explain/dicom/*` |
| PACS dcm4chee | WADO-RS `GET {PACS_BASE_URL}/studies/{study}/series/{series}/instances/{sop}`, `Accept: multipart/related; type="application/dicom"`, таймауты connect 5 с / read 30 с, разбор multipart, фолбэк на сырой DICOM | `/predict/pacs/`, `/metadata/pacs/`, `/explain/pacs/*` |
| WFDB (PTB-XL) | `wfdb.rdsamp` из `WFDB_ROOT` | `/predict/wfdb/` — только внутренняя валидация |

Метаданные (`sources/dicom_metadata.py`): теги пациента/исследования/устройства,
`WaveformAnnotationSequence` → числовые измерения (код SCPECG, значение, единица) с пометкой
вольтажных критериев ГЛЖ (RV5, SV1, RV6, SV2) и текстовые заключения аппарата.

## 6. База данных

PostgreSQL, `pgcloud.tech-uic.uz:5433`, база `ai_ecg`, доступ по `DATABASE_URL`
(`postgresql+asyncpg://…`). Используется **только модулем аннотаций**; предсказания в БД
не сохраняются.

Схема создаётся при старте через `Base.metadata.create_all` (без Alembic — миграций пока нет),
затем идемпотентный seed.

```
annotation_classes                       annotations
  id            uuid PK                    id                  uuid PK
  type          enum superclass|subclass   study_instance_uid  text, index
  code          text unique                series_instance_uid text null
  names         jsonb {ru, uz, ...}        sop_instance_uid    text null
  parent_class_id uuid FK → self (null)    doctor_id           text null (auth нет)
  is_custom     bool                       other_text          text null
  is_active     bool (soft delete)         is_active           bool (soft delete)
  created_by    text null                  created_at / updated_at timestamptz
  created_at    timestamptz
                                         annotation_class_links (M:N)
                                           annotation_id uuid FK → annotations ON DELETE CASCADE
                                           class_id      uuid FK → annotation_classes
```

Правила: подкласс привязан ровно к одному суперклассу; удаление классов и аннотаций — мягкое;
одно исследование может иметь несколько аннотаций (разные врачи); PUT полностью заменяет
набор классов, истории изменений нет.

Пул: `pool_size=3, max_overflow=5, pool_pre_ping, pool_recycle=180 с`, таймауты соединения
и запроса 10 с (введены после инцидентов с обрывом простаивающих соединений через NAT).
`check_db_connectivity.py` — отдельный диагностический скрипт для проверки стабильности канала.

## 7. Сторонние системы и зависимости

| Система | Роль | Направление |
|---|---|---|
| PACS dcm4chee-arc (`195.158.10.39:8080`) | источник DICOM по UID | backend → PACS (HTTP) |
| PostgreSQL pgcloud (`pgcloud.tech-uic.uz:5433`) | аннотации | backend → DB |
| Graylog | сбор логов из stdout контейнера | pod → Graylog |
| GitLab CI (`git.uzinfocom.uz`) + Harbor | сборка и хранение образа | CI |
| GitOps-репозиторий `core/manifests/moh/ai-ecg`, Kubernetes | деплой (kustomize overlays dev/prod) | CI → k8s |
| ECGFounder (открытые веса) | претрейн-модель | файлы в репозитории |
| PTB-XL (открытый датасет) | данные файнтюна и порогов | вне репозитория |

Внешних SaaS/облачных API нет; все вызовы — внутри контура.

## 8. Конфигурация (переменные окружения)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | — (обязательна) | `postgresql+asyncpg://user:pass@host:port/db` |
| `PACS_BASE_URL` | `http://195.158.10.39:8080/dcm4chee-arc/aets/DCM4CHEE/rs` | WADO-RS |
| `PACS_TIMEOUT_CONNECT` / `PACS_TIMEOUT_READ` | 5 / 30 | секунды |
| `DEVICE` / `USE_GPU` | `cuda` если `USE_GPU=1` | фолбэк на CPU, если CUDA недоступна |
| `SUPERCLASSES` | `NORM,MI,CD,HYP,STTC` | порядок выходов дообученной модели |
| `NUM_LEAD` | 12 | |
| `TARGET_FS` / `TARGET_DURATION_SEC` | 500 / 10.0 | должны совпадать с трейном |
| `NUM_CLASSES_150` / `TOP_K_150` | 150 / 10 | |
| `WFDB_ROOT` | `./wfdb_data` | |
| `LOG_LEVEL` | INFO | консоль; файл всегда WARNING+ |
| `LOG_FILE_MAX_BYTES` / `LOG_FILE_BACKUP_COUNT` | 10 МБ / 5 | ротация `logs/app.log` |
| `PORT` | 8000 | только для `uv run app.py` |
| `APP_ENV` | development | |

Пути к весам захардкожены относительно корня проекта (`weights/...`).

## 9. Логирование и мониторинг

- Консоль (stdout → Graylog): всё от `LOG_LEVEL`, формат
  `time | LEVEL | logger | req=<id> | file:line:func | message`. INFO-записи health-проб
  k8s (`/api/health`) отфильтрованы, чтобы не забивать Graylog; WARNING+ по ним проходят.
- Файл `logs/app.log` внутри pod: только WARNING+, расширенный формат (полный путь, PID/TID),
  ротация; отдаётся целиком через `GET /api/logs/download/`.
- Логи uvicorn идут через тот же форматтер (без дублирования).
- Время в строках — UTC контейнера.
- Health: `GET /api/health` (и `/api/health/`) — используется пробами k8s и Docker `HEALTHCHECK`.

## 10. Сборка и деплой

- `Dockerfile`: `python:3.12-slim`, `uv sync --frozen --no-dev`, копируются код и `weights/`,
  non-root пользователь, `HEALTHCHECK` на `/api/health/`, запуск
  `uvicorn app:app --workers 1`. Образ тяжёлый из-за весов (~0.5 ГБ) и torch.
- `.gitlab-ci.yml`: стадии `build` (docker build с кэшем → push в Harbor `:dev`/`:prod`) и
  `deploy` (клонирует GitOps-репозиторий, через `yq` подставляет тег образа в
  `gitops/backend/overlays/{dev|prod}/kustomization.yaml`, коммитит в `main` — дальше
  ArgoCD/Flux применяет). `dev` — автоматически, `main` — вручную.
- 1 worker и singleton-модели: горизонтальное масштабирование — репликами pod, не воркерами.

## 11. Известные ограничения и риски

| # | Что | Последствие | Что делать |
|---|---|---|---|
| 1 | Нет аутентификации, CORS `*` | любой, кто видит URL, может дёргать API, читать аннотации, скачивать логи | API-key/JWT на роутерах, закрыть `/logs/download/` |
| 2 | `/logs/download/` и INFO-логи содержат имена файлов и UID | потенциальный PHI в логах | не логировать имена файлов, закрыть эндпоинт |
| 3 | `thresholds.json` не выложен | пороги 0.5 вместо откалиброванных | экспортировать через `export_thresholds.py`, положить в `weights/ecg_signal/` |
| 4 | `filter_ecg` в `train_utils.py` изменён (HP 0.5/LP 40 вместо HP 1/LP 30) и не закоммичен | препроцессинг инференса может не совпадать с тем, на котором обучен `best.pth` | подтвердить, на каком фильтре обучены текущие веса, синхронизировать |
| 5 | Инференс в `async def` эндпоинтах выполняется в event loop | один тяжёлый запрос блокирует остальные | `run_in_threadpool` для инференса/объяснений |
| 6 | Веса в git без LFS (~490 МБ) | тяжёлый клон и образ | git LFS или отдельное хранилище артефактов |
| 7 | `create_all` вместо миграций | изменение схемы вручную | Alembic, когда схема стабилизируется |
| 8 | `doctor_id` — свободная строка | нет связи с реальным пользователем | после подключения auth брать из токена |
| 9 | Ноутбук файнтюна и `thresholds` вне репозитория | невоспроизводимость модели | вынести в отдельный ML-репозиторий с фиксированными данными/сидом |
