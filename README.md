# ECG AI Service — запуск

## 1. Структура проекта

```
ecg_backend/
├── app.py
├── core/            # config, logging, middleware, errors, request_context, schemas
├── models/
│   ├── ecg_signal/          # дообученная модель (5 классов) + explainability
│   └── ecg_signal_raw150/   # исходная ECGFounder (150 классов претрейна)
├── sources/          # DICOM/PACS/WFDB - извлечение сырых данных
├── routers/           # HTTP-эндпоинты
├── weights/
│   ├── ecg_signal/            # best.pth + thresholds.json (дообученная модель)
│   └── ecgfounder_150/         # 12_lead_ECGFounder.pth + tasks.txt (исходная модель)
├── logs/               # создаётся автоматически
├── requirements.txt
└── .env.example
```

## 2. Установка

```bash
uv venv
uv pip install -r requirements.txt
```

Команды ниже подразумевают запуск через `uv run ...` (использует `.venv` проекта автоматически, отдельно активировать не нужно).


## 3. Запуск

```bash
uv run app.py
```

или напрямую:

```bash
uv run uvicorn app:app --host 127.0.0.1 --port 8000
```


Проверка: `GET http://127.0.0.1:8000/api/health` → `{"status": "ok"}`
Swagger UI: `http://127.0.0.1:8000/docs`

## 4. Основные эндпоинты

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/api/predict/dicom` | Предсказание (5 классов) по загруженному DICOM |
| POST | `/api/predict/pacs` | То же, DICOM забирается с PACS по UID'ам |
| POST | `/api/predict/wfdb` | Предсказание по WFDB-записи (внутренний пайплайн) |
| POST | `/api/predict/dicom/raw150` | Предсказание исходной ECGFounder (150 классов, без порогов) |
| POST | `/api/metadata/dicom` | Демография/измерения/заключения из DICOM |
| POST | `/api/explain/dicom` | Grad-CAM++ + Integrated Gradients по каждому positive-классу (JSON) |
| POST | `/api/explain/dicom/image?class_name=MI` | То же, готовый PNG для одного класса |
| GET | `/api/logs/download` | Скачать файл логов (WARNING+) |

## 5. Логи

Консоль — всё от `LOG_LEVEL` (по умолчанию INFO). Файл `logs/app.log` — только WARNING+, ротация по размеру. Каждый запрос помечен `request_id` — по нему можно проследить всю цепочку вызовов одного запроса в логе.
