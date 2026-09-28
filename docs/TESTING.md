# ECG AI Service — ручное тестирование

Документ для проверки работоспособности бэкенда без участия разработчика.
Все команды проверены на реальном сервисе (см. дату в конце).

## 1. Что нужно для проверки

| Что | Где взять |
|---|---|
| Адрес сервиса | dev: `https://api-ecg-ai.med-uic.uz/api`, prod: `https://api-ecg-ai.ssv.uz/api`, локально: `http://127.0.0.1:8000/api` |
| Swagger UI | `{base_url без /api}/docs` — все запросы ниже можно выполнить из браузера, curl не обязателен |
| Тестовый DICOM | В репозитории: `ecg_output/1.3.6.1.4.1.34556.1.2444018079341608150430873424343174823938.dcm` (EDAN SE-1515, 1000 Гц, 12 отведений, норма) |
| UID для PACS | Любое ЭКГ-исследование в dcm4chee (`PACS_BASE_URL` в `.env`) — нужны `studyInstanceUID`, `seriesInstanceUID`, `sopInstanceUID` |
| Доступ к сети | PACS (`195.158.10.39:8080`) и PostgreSQL (`pgcloud.tech-uic.uz:5433`) доступны только из внутренней сети/VPN |

Аутентификации в API сейчас нет — все эндпоинты открыты.

Ниже `$B` — базовый URL с `/api`, `$D` — путь к тестовому DICOM:

```bash
B=https://api-ecg-ai.med-uic.uz/api
D=ecg_output/1.3.6.1.4.1.34556.1.2444018079341608150430873424343174823938.dcm
```

> **Windows / Git Bash.** Кириллица в аргументе `-d '...'` уходит в cp1251 и сервер отвечает
> `{"detail": "There was an error parsing the body"}`. Тела с кириллицей сохраняйте в файл
> в UTF-8 и передавайте через `--data-binary @file.json`. Для чтения ответов с кириллицей в
> консоли используйте `PYTHONIOENCODING=utf-8` или Swagger UI.

## 2. Локальный запуск (если проверяете не на стенде)

```bash
uv sync                       # Python 3.12, зависимости из uv.lock
cp .env.example .env          # + добавить DATABASE_URL=postgresql+asyncpg://user:pass@host:5433/ai_ecg
uv run app.py                 # или: uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

Ожидаемый лог старта (порядок важен — так видно, на каком шаге упало):

```
app | Запуск приложения - загрузка модели...
models.ecg_signal.model_service | Model loaded on cpu, classes=['NORM', 'MI', 'CD', 'HYP', 'STTC'], thresholds={...}
models.ecg_signal_raw150.model_service_raw150 | Исходная ECGFounder (150 классов) загружена на cpu
app | Модель загружена за 0.68 секунд
db.seed | Дефолтные классы аннотаций проверены/добавлены (6 суперклассов, 149 подклассов)
uvicorn.error | Application startup complete.
```

Если `WARNING ... thresholds.json не найден` — это ожидаемо на текущий момент: файл порогов
не выложен, для всех 5 классов используется порог 0.5 (см. раздел 9).

Если старт падает на шаге после «Модель загружена» — недоступна БД (проверить `DATABASE_URL`,
VPN; отдельно `uv run check_db_connectivity.py`).

## 3. Health и Swagger

| Шаг | Команда | Ожидается |
|---|---|---|
| 3.1 | `curl -i $B/health` | `200`, тело `{"status":"ok"}`, заголовок `x-request-id: <8 hex>` |
| 3.2 | `curl -i $B/health/` | `200` (без редиректа 307) |
| 3.3 | Открыть `/docs` в браузере | Swagger UI, 19 путей в группах `ecg-signal`, `logs`, `annotation` |
| 3.4 | `curl $B/../openapi.json` | JSON со схемой |

## 4. Предсказание по DICOM (основная функция)

### 4.1 `/predict/dicom/` — 5 классов с порогами

```bash
curl -s -X POST $B/predict/dicom/ -F "file=@$D"
```

Ожидаемый ответ на тестовом файле (вероятности могут отличаться в 3-м знаке):

```json
{
  "predictions": [
    {"label": "NORM", "name": {"ru": "Норма", "uz": "Norma"}, "probability": 0.981, "threshold": 0.5, "positive": true},
    {"label": "MI",   "name": {"ru": "Инфаркт миокарда", "uz": "Miokard infarkti"}, "probability": 0.006, "threshold": 0.5, "positive": false},
    {"label": "CD",   "name": {"ru": "Нарушения проводимости", "uz": "..."}, "probability": 0.012, "threshold": 0.5, "positive": false},
    {"label": "HYP",  "name": {"ru": "Гипертрофия", "uz": "Gipertrofiya"}, "probability": 0.021, "threshold": 0.5, "positive": false},
    {"label": "STTC", "name": {"ru": "Изменения ST/T", "uz": "ST/T o'zgarishlari"}, "probability": 0.016, "threshold": 0.5, "positive": false}
  ],
  "positive_classes": ["NORM"],
  "source": {"filename": "1.3.6.1.4.1.34556....dcm", "fs": 1000.0}
}
```

Что проверить:
- ровно 5 элементов в `predictions`, порядок NORM, MI, CD, HYP, STTC;
- `positive == (probability >= threshold)` для каждого;
- `positive_classes` = список `label` с `positive: true`;
- `source.fs` совпадает с частотой дискретизации файла (1000 для тестового);
- время ответа на CPU — до 2 с.

### 4.2 `/predict/dicom/raw150/` — исходная модель, 150 классов, без порогов

```bash
curl -s -X POST $B/predict/dicom/raw150/ -F "file=@$D"
```

Ожидается: `predictions` — 150 элементов `{name, label, probability}`; `top_k` — 10 элементов,
отсортированных по убыванию вероятности. На тестовом файле top-3:

```
NORMAL SINUS RHYTHM      0.999
SINUS RHYTHM             0.998
LEFT ATRIAL ENLARGEMENT  0.969
```

### 4.3 `/predict/pacs/` и `/predict/pacs/raw150/` — то же, DICOM забирается с PACS

```bash
curl -s -X POST $B/predict/pacs/ -H "Content-Type: application/json" \
  -d '{"studyInstanceUID":"<uid>","seriesInstanceUID":"<uid>","sopInstanceUID":"<uid>"}'
```

Ожидается: тот же формат, что в 4.1, `source` содержит три UID и `fs`.
С несуществующими UID (`1.2.3`) — `502`:

```json
{"detail": "Ошибка запроса к PACS: 404 Client Error: Not Found for url: http://195.158.10.39:8080/.../instances/1.2.3"}
```

Если PACS недоступен по сети — `502` с `Timeout при обращении к PACS` через
`PACS_TIMEOUT_CONNECT` (5 с).

### 4.4 `/predict/wfdb/` — внутренний пайплайн (PTB-XL, не для пользователей)

```bash
curl -s -X POST $B/predict/wfdb/ -H "Content-Type: application/json" -d '{"record_name":"nope"}'
```

Ожидается `404`: `{"detail": "WFDB-запись не найдена: ./wfdb_data/nope.hea"}`.
На стенде `WFDB_ROOT` пуст, поэтому положительный сценарий проверяется только локально
с распакованным PTB-XL (`record_name` вида `records500/00000/00001_hr`).

## 5. Метаданные DICOM (без модели)

```bash
curl -s -X POST $B/metadata/dicom/ -F "file=@$D"
```

Ожидается на тестовом файле:

```json
{
  "patient": {"PatientID": "125966", "PatientSex": "F", "PatientAge": "046Y", ...},
  "study":   {"StudyInstanceUID": "1.3.6.1.4.1.34556.1.2537...", "StudyDate": "20251110", "StudyDescription": "RestingECG12Lead", ...},
  "device":  {"Manufacturer": "EDAN INSTRUMENTS CO., LTD.", "ManufacturerModelName": "SE-1515", ...},
  "measurements": [
    {"name": "Ventricular Heart Rate", "code": "5.10.2.5-1", "value": 88.0, "unit": "heart beats per minute", "is_voltage_criterion": false},
    {"name": "PR Interval", "value": 154.0, "unit": "millisecond", ...},
    {"name": "QRS Duration", "value": 86.0, "unit": "millisecond", ...},
    ...
  ],
  "text_annotations": ["Синусовый ритм\r\n***Нормальная ЭКГ***"]
}
```

Что проверить: заполнены `patient`, `study`, `device`; `measurements` не пуст; у измерений
RV5/SV1/RV6/SV2 (если есть в файле) `is_voltage_criterion: true`.

`/metadata/pacs/` — тот же ответ по UID (тело как в 4.3).

## 6. Объяснимость (Grad-CAM++ × Integrated Gradients)

Объяснение строится только для классов, которые модель признала положительными
в 5-классовой модели. Для тестового файла это `NORM`.

### 6.1 `/explain/dicom/` — числовые карты (JSON)

```bash
curl -s -X POST $B/explain/dicom/ -F "file=@$D" | python -c "import json,sys; d=json.load(sys.stdin); print(d['positive_classes'], d['fs'], len(d['display_signal']), len(d['display_signal'][0]))"
```

Ожидается: `['NORM'] 500 12 5000`. В `explanations.NORM`:
- `grad_cam` — массив 5000 (общий на все отведения, значения 0..1);
- `integrated_gradients` — 12 × 5000 (может быть отрицательным);
- `combined` — 12 × 5000, значения 0..1.

Время ответа на CPU — 2–4 с (два forward/backward на каждый положительный класс). Ответ большой (~2 МБ).

### 6.2 `/explain/dicom/image/?class_name=NORM` — готовый PNG

```bash
curl -s -X POST "$B/explain/dicom/image/?class_name=NORM" -F "file=@$D" -o explain.png
```

Ожидается: `200`, `Content-Type: image/png`, ~400 КБ. На картинке 12 отведений в сетке 6×2,
заголовок `Норма (p=0.98) - объяснение: Grad-CAM++ x Integrated Gradients`, поверх кривых —
жёлто-красная теплокарта.

Отрицательный сценарий — класс, который не положителен:

```bash
curl -s -X POST "$B/explain/dicom/image/?class_name=MI" -F "file=@$D"
```

Ожидается `404`: `{"detail": "Класс 'MI' не является положительным для этой записи. Положительные классы: ['NORM']"}`.

`/explain/pacs/` и `/explain/pacs/image/?class_name=...` — то же по UID.

## 7. Ошибки входных данных

| Шаг | Команда | Ожидается |
|---|---|---|
| 7.1 | `curl -s -X POST $B/predict/dicom/ -F "file=@pyproject.toml"` | `400`, `Файл не является корректным DICOM: ...` |
| 7.2 | DICOM-изображение ЭКГ (скан), а не waveform | `400`, `В DICOM нет WaveformSequence - это не ЭКГ-waveform запись` |
| 7.3 | DICOM с < 12 отведений | `400`, `В сигнале не хватает отведений: [...]` |
| 7.4 | `curl -s -X POST $B/predict/dicom/` (без файла) | `422`, стандартная ошибка валидации FastAPI |

## 8. Аннотации врача (PostgreSQL)

Последовательность ниже — полный цикл; выполнять по порядку. `lang=ru|uz` меняет только
поле `name`, `code` неизменен.

### 8.1 Справочник классов

```bash
curl -s "$B/annotation/classes/?lang=ru"
```

Ожидается: массив из 6 суперклассов (NORM, MI, CD, HYP, STTC, OTHER) + возможно кастомные,
у каждого вложенный `subclasses`. Фрагмент:

```json
{"id": "cbb12114-...", "code": "NORM", "name": "Норма", "is_custom": false,
 "subclasses": [{"id": "acb0f49a-...", "type": "subclass", "code": "NORM_ABNORMAL_ECG", "name": "Аномальная ЭКГ", "parent_class_id": "cbb12114-...", "is_custom": false}, ...]}
```

Сохраните `id` любого суперкласса (`SC`) и одного его подкласса (`SUB`) для следующих шагов.

### 8.2 Создать аннотацию

`ann.json` (UTF-8):

```json
{"study_instance_uid": "TEST.DOC.1", "doctor_id": "doc_test",
 "superclass_ids": ["<SC>"], "subclass_ids": ["<SUB>"], "other_text": "проверка"}
```

```bash
curl -s -X POST "$B/annotation/?lang=ru" -H "Content-Type: application/json" --data-binary @ann.json
```

Ожидается `201`, объект с `id`, `superclasses[0].code`, `subclasses[0].code`, `created_at == updated_at`.
Сохраните `id` (`AID`).

### 8.3 Чтение

| Команда | Ожидается |
|---|---|
| `curl -s "$B/annotation/study/TEST.DOC.1/"` | массив, содержит созданную аннотацию |
| `curl -s "$B/annotation/$AID/"` | тот же объект |
| `curl -s "$B/annotation/?limit=2&doctor_id=doc_test"` | массив ≤ 2, все с `doctor_id: doc_test` |

### 8.4 Обновить (PUT = полная замена)

Тот же `ann.json` с `"other_text": "обновлено"`:

```bash
curl -s -X PUT "$B/annotation/$AID/" -H "Content-Type: application/json" --data-binary @ann2.json
```

Ожидается `200`, `other_text: "обновлено"`, `updated_at > created_at`.

### 8.5 Ошибки валидации

| Тело | Ожидается |
|---|---|
| `superclass_ids: []` | `422`, `List should have at least 1 item after validation, not 0` |
| подкласс в `superclass_ids` | `400`, `Ожидался тип superclass, получены: ['NORM_ABNORMAL_ECG']` |
| несуществующий uuid | `400`, `Классы не найдены: {...}` |

### 8.6 Кастомный класс: создать → удалить → проверить → восстановить

`cls.json`: `{"type": "subclass", "names": {"ru": "Тестовый подкласс", "uz": "Test subklass"}, "parent_class_id": "<SC>"}`

```bash
curl -s -X POST "$B/annotation/classes/?lang=uz" -H "Content-Type: application/json" --data-binary @cls.json
```

Ожидается `201`: `code` сгенерирован транслитерацией — `TESTOVYY_PODKLASS`, `name: "Test subklass"`, `is_custom: true`. Сохраните `id` (`CID`).

| Шаг | Команда | Ожидается |
|---|---|---|
| удалить | `curl -X DELETE "$B/annotation/classes/$CID/"` | `204` |
| нет в списке | `curl "$B/annotation/classes/"` | `CID` отсутствует |
| есть с флагом | `curl "$B/annotation/classes/?include_inactive=true"` | `CID` присутствует |
| нельзя использовать | POST аннотации с `subclass_ids: [CID]` | `400`, `Классы неактивны (удалены): ['TESTOVYY_PODKLASS']` |
| восстановить | `curl -X POST "$B/annotation/classes/$CID/activate/"` | `200`, объект класса |
| удалить снова | `curl -X DELETE "$B/annotation/classes/$CID/"` | `204` (уборка) |

Удаление — мягкое (`is_active=false`), строки в БД остаются. После проверки в таблице
`annotation_classes` останется неактивный `TESTOVYY_PODKLASS` — это нормально.

### 8.7 Удалить аннотацию

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE "$B/annotation/$AID/"   # 204
curl -s "$B/annotation/$AID/"                                              # 404 {"detail": "Аннотация не найдена"}
```

## 9. Логи

| Шаг | Что | Ожидается |
|---|---|---|
| 9.1 | `curl -s $B/logs/download/ -o app.log` | `200`, `text/plain`; файл содержит только WARNING+ с полным путём/строкой/`req=` |
| 9.2 | В Graylog по `req=<x-request-id>` из ответа 4.1 | строки `--> POST /api/predict/dicom/` и `<-- ... 200 (N ms)` от `core.middleware` + строка `uvicorn.access` |
| 9.3 | В Graylog по `/api/health` | INFO-строк нет (пробы k8s отфильтрованы), только WARNING+ если проба падала |

Обратите внимание: время в строке лога — UTC контейнера, Graylog показывает локальное
(Ташкент, +5 ч).

## 10. Чек-лист

| # | Проверка | ОК |
|---|---|---|
| 1 | `/health` и `/health/` → 200 без редиректа | ☐ |
| 2 | Swagger `/docs` открывается, 19 путей | ☐ |
| 3 | `/predict/dicom/` на тестовом файле → NORM положителен, p ≈ 0.98 | ☐ |
| 4 | `/predict/dicom/raw150/` → 150 классов, top-1 NORMAL SINUS RHYTHM | ☐ |
| 5 | `/predict/pacs/` с реальными UID → 200; с `1.2.3` → 502 | ☐ |
| 6 | `/metadata/dicom/` → пациент/устройство/измерения/заключение | ☐ |
| 7 | `/explain/dicom/` → карты 5000 / 12×5000 для NORM | ☐ |
| 8 | `/explain/dicom/image/?class_name=NORM` → PNG; `MI` → 404 | ☐ |
| 9 | Не-DICOM → 400 | ☐ |
| 10 | Классы аннотаций: 6 суперклассов, подклассы вложены | ☐ |
| 11 | Аннотация: POST 201 → GET → PUT → DELETE 204 → GET 404 | ☐ |
| 12 | Кастомный класс: создание, soft-delete, `include_inactive`, activate | ☐ |
| 13 | `/logs/download/` → файл; `req=` из ответа находится в Graylog | ☐ |

## 11. Известные особенности на момент проверки

- `weights/ecg_signal/thresholds.json` отсутствует → пороги 0.5 для всех классов; после
  выкладки файла значения `threshold` в ответе изменятся, `positive` может измениться.
- Аутентификации нет; `/logs/download/` открыт — не выносить наружу без auth.
- На стенде модель работает на CPU (`DEVICE=cuda` в `.env` игнорируется, если CUDA недоступна —
  в логе старта `Model loaded on cpu`).

Последняя полная прогонка: 2026-09-17, локально (CPU, dev-БД `ai_ecg`), все пункты чек-листа кроме 5 (PACS — только негативный сценарий) пройдены.
