import logging
from fastapi import APIRouter, File, HTTPException, Response, UploadFile, Query
import torch

from core.config import settings
from core.schemas import (
    MetadataResponse,
    PacsRequest,
    PredictionResponse,
    RawClassPrediction,
    RawPredictionResponse,
    WfdbRequest,
)
from models.ecg_signal.model_service import ModelService
from models.ecg_signal.preprocessing import (
    preprocess_raw_signal,
    reorder_leads,
    preprocess_for_display,
)
from models.ecg_signal_raw150.model_service_raw150 import RawECGFounderService
from models.ecg_signal.explain_rendering import render_explanation_png
from models.ecg_signal.explainability import explain_class

from sources.dicom_metadata import extract_metadata_from_dicom_bytes
from sources.dicom_signal import extract_signal_from_dicom_bytes
from sources.pacs_client import fetch_dicom_from_pacs, PacsFetchError
from sources.wfdb_service import extract_signal_from_wfdb

from core.diagnostic_labels import translate_label_all, translate_label_all_raw150

router = APIRouter()

logger = logging.getLogger(__name__)


def _build_response(predictions: list[dict], source: dict) -> PredictionResponse:
    for p in predictions:
        p["name"] = translate_label_all(p["label"])
    positive = [p["label"] for p in predictions if p["positive"]]
    return PredictionResponse(
        predictions=predictions, positive_classes=positive, source=source
    )


@router.post("/predict/dicom/", response_model=PredictionResponse)
async def predict_dicom(file: UploadFile = File(...)):
    """Принимает DICOM-файл с сырым waveform (не картинку!) и предсказывает по нему."""
    dicom_bytes = await file.read()
    try:
        extracted = extract_signal_from_dicom_bytes(dicom_bytes)
        ordered = reorder_leads(extracted.signal, extracted.lead_names)
        processed = preprocess_raw_signal(ordered, extracted.fs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка обработки DICOM")
        raise HTTPException(status_code=500, detail=f"Не удалось обработать DICOM: {e}")

    predictions = ModelService.get_instance().predict(processed)
    return _build_response(
        predictions, source={"filename": file.filename, "fs": extracted.fs}
    )


@router.post("/predict/pacs/", response_model=PredictionResponse)
def predict_pacs(req: PacsRequest):
    """Забирает DICOM waveform с PACS по UID'ам и предсказывает по нему."""
    try:
        dicom_bytes = fetch_dicom_from_pacs(
            req.studyInstanceUID, req.seriesInstanceUID, req.sopInstanceUID
        )
    except PacsFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        extracted = extract_signal_from_dicom_bytes(dicom_bytes)
        ordered = reorder_leads(extracted.signal, extracted.lead_names)
        processed = preprocess_raw_signal(ordered, extracted.fs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка обработки DICOM с PACS")
        raise HTTPException(
            status_code=500, detail=f"Не удалось обработать DICOM с PACS: {e}"
        )

    predictions = ModelService.get_instance().predict(processed)
    return _build_response(
        predictions,
        source={
            "studyInstanceUID": req.studyInstanceUID,
            "seriesInstanceUID": req.seriesInstanceUID,
            "sopInstanceUID": req.sopInstanceUID,
            "fs": extracted.fs,
        },
    )


@router.post("/predict/wfdb/", response_model=PredictionResponse)
def predict_wfdb(req: WfdbRequest):
    """Внутренний пайплайн: предсказание по WFDB-записи (.hea/.dat) внутри WFDB_ROOT."""
    try:
        signal, fs = extract_signal_from_wfdb(req.record_name)
        processed = preprocess_raw_signal(signal, fs)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка обработки WFDB-записи")
        raise HTTPException(
            status_code=500, detail=f"Не удалось обработать WFDB-запись: {e}"
        )

    predictions = ModelService.get_instance().predict(processed)
    return _build_response(
        predictions, source={"record_name": req.record_name, "fs": fs}
    )


@router.post("/metadata/dicom/", response_model=MetadataResponse)
async def metadata_dicom(file: UploadFile = File(...)):
    """
    Клинические метаданные из DICOM (демография, измерения аппарата, текстовые
    заключения) - НЕ предсказание модели. Отдельный лёгкий эндпоинт: не грузит
    сигнал через модель, только парсит структурные теги.
    """
    logger.info("Получен DICOM для извлечения метаданных: %s", file.filename)
    dicom_bytes = await file.read()
    try:
        metadata = extract_metadata_from_dicom_bytes(dicom_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка извлечения метаданных из DICOM")
        raise HTTPException(
            status_code=500, detail=f"Не удалось извлечь метаданные: {e}"
        )
    return MetadataResponse(**metadata)


@router.post("/metadata/pacs/", response_model=MetadataResponse)
def metadata_pacs(req: PacsRequest):
    """То же самое, но DICOM забирается с PACS по UID'ам."""
    try:
        dicom_bytes = fetch_dicom_from_pacs(
            req.studyInstanceUID, req.seriesInstanceUID, req.sopInstanceUID
        )
    except PacsFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        metadata = extract_metadata_from_dicom_bytes(dicom_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка извлечения метаданных из DICOM с PACS")
        raise HTTPException(
            status_code=500, detail=f"Не удалось извлечь метаданные: {e}"
        )
    return MetadataResponse(**metadata)


def _build_raw150_response(
    predictions: list[dict], source: dict
) -> RawPredictionResponse:
    for p in predictions:
        p["name"] = translate_label_all_raw150(p["label"])

    top_k = sorted(predictions, key=lambda p: p["probability"], reverse=True)[
        : settings.TOP_K_150
    ]
    return RawPredictionResponse(
        predictions=[RawClassPrediction(**p) for p in predictions],
        top_k=[RawClassPrediction(**p) for p in top_k],
        source=source,
    )


@router.post("/predict/dicom/raw150/", response_model=RawPredictionResponse)
async def predict_dicom_raw150(file: UploadFile = File(...)):
    """
    Предсказание ИСХОДНОЙ ECGFounder (150 классов претрейна, до файнтюна).
    Возвращает сырые вероятности по всем 150 классам - порогов для них нет,
    решение о "положительности" остаётся на клиенте/враче.
    """
    logger.info(
        "Получен DICOM для предсказания исходной ECGFounder (150 классов): %s",
        file.filename,
    )
    dicom_bytes = await file.read()
    try:
        extracted = extract_signal_from_dicom_bytes(dicom_bytes)
        ordered = reorder_leads(extracted.signal, extracted.lead_names)
        processed = preprocess_raw_signal(ordered, extracted.fs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка обработки DICOM")
        raise HTTPException(status_code=500, detail=f"Не удалось обработать DICOM: {e}")

    predictions = RawECGFounderService.get_instance().predict(processed)
    return _build_raw150_response(
        predictions, source={"filename": file.filename, "fs": extracted.fs}
    )


@router.post("/predict/pacs/raw150/", response_model=RawPredictionResponse)
def predict_pacs_raw150(req: PacsRequest):
    """То же самое (150 классов претрейна), но DICOM забирается с PACS по UID'ам."""
    try:
        dicom_bytes = fetch_dicom_from_pacs(
            req.studyInstanceUID, req.seriesInstanceUID, req.sopInstanceUID
        )
    except PacsFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        extracted = extract_signal_from_dicom_bytes(dicom_bytes)
        ordered = reorder_leads(extracted.signal, extracted.lead_names)
        processed = preprocess_raw_signal(ordered, extracted.fs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка обработки DICOM с PACS")
        raise HTTPException(
            status_code=500, detail=f"Не удалось обработать DICOM с PACS: {e}"
        )

    predictions = RawECGFounderService.get_instance().predict(processed)
    return _build_raw150_response(
        predictions,
        source={
            "studyInstanceUID": req.studyInstanceUID,
            "seriesInstanceUID": req.seriesInstanceUID,
            "sopInstanceUID": req.sopInstanceUID,
            "fs": extracted.fs,
        },
    )


# ----------------------------------------------------------------------------
# Объяснимость (Grad-CAM++ + Integrated Gradients) - только для 5-классовой
# дообученной модели: у неё есть откалиброванные пороги (positive/negative),
# то есть понятно, ДЛЯ КАКИХ классов объяснение вообще имеет смысл строить.
# У исходной 150-классовой модели порогов нет - см. RawECGFounderService.
# ----------------------------------------------------------------------------


def _explain_from_dicom_bytes(dicom_bytes: bytes, filename: str) -> dict:
    """Общая часть для /explain/dicom и /explain/dicom/image: сигнал -> предсказание -> explain на каждый positive-класс."""
    extracted = extract_signal_from_dicom_bytes(dicom_bytes)
    ordered = reorder_leads(extracted.signal, extracted.lead_names)

    model_input = preprocess_raw_signal(
        ordered, extracted.fs
    )  # [12, TARGET_LEN], z-scored - для модели
    display_signal = preprocess_for_display(
        ordered, extracted.fs
    )  # [12, TARGET_LEN], мВ - для графика

    service = ModelService.get_instance()
    predictions = service.predict(model_input)
    positive = [p for p in predictions if p["positive"]]

    if not positive:
        return {
            "predictions": predictions,
            "positive_classes": [],
            "explanations": {},
            "display_signal": display_signal,
            "fs": settings.TARGET_FS,
            "source": {"filename": filename, "fs": extracted.fs},
        }

    x = torch.from_numpy(model_input).unsqueeze(0).to(service.device)
    target_layer = service.model.stage_list[
        -2
    ]  # см. explainability.py - компромисс глубина/разрешение

    explanations = {}
    for p in positive:
        class_idx = service.class_names.index(p["label"])
        explanations[p["label"]] = explain_class(
            service.model,
            target_layer,
            x,
            class_idx,
            target_len=model_input.shape[
                1
            ],  # = TARGET_LEN, карта в той же сетке, что и display_signal
        )

    return {
        "predictions": predictions,
        "positive_classes": [p["label"] for p in positive],
        "explanations": explanations,
        "display_signal": display_signal,
        "fs": settings.TARGET_FS,
        "source": {"filename": filename, "fs": extracted.fs},
    }


@router.post("/explain/dicom/")
async def explain_dicom(file: UploadFile = File(...)):
    """
    Для КАЖДОГО положительного класса из предсказания - Grad-CAM++, Integrated
    Gradients и их комбинация. Возвращает числовые массивы (для собственного
    рендера на фронтенде); готовую картинку см. в /explain/dicom/image.
    """
    dicom_bytes = await file.read()
    try:
        result = _explain_from_dicom_bytes(dicom_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка построения объяснения для DICOM")
        raise HTTPException(
            status_code=500, detail=f"Не удалось построить объяснение: {e}"
        )

    return {
        "predictions": result["predictions"],
        "positive_classes": result["positive_classes"],
        "display_signal": result[
            "display_signal"
        ].tolist(),  # [12, N] мВ - для отрисовки кривой на фронте
        "fs": result["fs"],
        "explanations": {
            label: {
                "name": translate_label_all(label),
                "grad_cam": exp["grad_cam"].tolist(),
                "integrated_gradients": exp["integrated_gradients"].tolist(),
                "combined": exp["combined"].tolist(),
            }
            for label, exp in result["explanations"].items()
        },
        "source": result["source"],
    }


@router.post("/explain/dicom/image/")
async def explain_dicom_image(
    file: UploadFile = File(...),
    class_name: str = Query(..., description="Один из положительных классов, напр. MI"),
):
    """
    То же самое, но для ОДНОГО указанного класса - готовая PNG-картинка:
    12 отведений, поверх каждого - теплокарта важности (Grad-CAM++ x IG).
    """
    dicom_bytes = await file.read()
    try:
        result = _explain_from_dicom_bytes(dicom_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка построения объяснения для DICOM")
        raise HTTPException(
            status_code=500, detail=f"Не удалось построить объяснение: {e}"
        )

    if class_name not in result["explanations"]:
        available = result["positive_classes"]
        raise HTTPException(
            status_code=404,
            detail=f"Класс '{class_name}' не является положительным для этой записи. "
            f"Положительные классы: {available}",
        )

    prob = next(
        p["probability"] for p in result["predictions"] if p["label"] == class_name
    )
    lead_names = [
        "I",
        "II",
        "III",
        "aVR",
        "aVL",
        "aVF",
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
        "V6",
    ]

    png_bytes = render_explanation_png(
        signal_mV=result["display_signal"],
        fs=result["fs"],
        lead_names=lead_names,
        combined_map=result["explanations"][class_name]["combined"],
        class_name=translate_label_all(class_name)["ru"],
        probability=prob,
    )
    return Response(content=png_bytes, media_type="image/png")


@router.post("/explain/pacs/")
def explain_pacs(req: PacsRequest):
    """
    То же самое, что /explain/dicom, но DICOM забирается с PACS
    по UID'ам.
    """
    try:
        dicom_bytes = fetch_dicom_from_pacs(
            req.studyInstanceUID,
            req.seriesInstanceUID,
            req.sopInstanceUID,
        )
    except PacsFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        result = _explain_from_dicom_bytes(
            dicom_bytes,
            filename=req.sopInstanceUID,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка построения объяснения для DICOM с PACS")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось построить объяснение: {e}",
        )

    return {
        "predictions": result["predictions"],
        "positive_classes": result["positive_classes"],
        "display_signal": result["display_signal"].tolist(),
        "fs": result["fs"],
        "explanations": {
            label: {
                "name": translate_label_all(label),
                "grad_cam": exp["grad_cam"].tolist(),
                "integrated_gradients": exp["integrated_gradients"].tolist(),
                "combined": exp["combined"].tolist(),
            }
            for label, exp in result["explanations"].items()
        },
        "source": result["source"],
    }


@router.post("/explain/pacs/image/")
def explain_pacs_image(
    req: PacsRequest,
    class_name: str = Query(..., description="Один из положительных классов, напр. MI"),
):
    """То же самое, что /explain/dicom/image/, но DICOM забирается с PACS по UID'ам."""
    try:
        dicom_bytes = fetch_dicom_from_pacs(
            req.studyInstanceUID, req.seriesInstanceUID, req.sopInstanceUID
        )
    except PacsFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))

    try:
        result = _explain_from_dicom_bytes(dicom_bytes, filename=req.sopInstanceUID)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка построения объяснения для DICOM с PACS")
        raise HTTPException(
            status_code=500, detail=f"Не удалось построить объяснение: {e}"
        )

    if class_name not in result["explanations"]:
        available = result["positive_classes"]
        raise HTTPException(
            status_code=404,
            detail=f"Класс '{class_name}' не является положительным для этой записи. "
            f"Положительные классы: {available}",
        )

    prob = next(
        p["probability"] for p in result["predictions"] if p["label"] == class_name
    )
    lead_names = [
        "I",
        "II",
        "III",
        "aVR",
        "aVL",
        "aVF",
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
        "V6",
    ]

    png_bytes = render_explanation_png(
        signal_mV=result["display_signal"],
        fs=result["fs"],
        lead_names=lead_names,
        combined_map=result["explanations"][class_name]["combined"],
        class_name=translate_label_all(class_name)["ru"],
        probability=prob,
    )
    return Response(content=png_bytes, media_type="image/png")
