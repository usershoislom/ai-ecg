"""
dicom_metadata.py

Извлекает из DICOM всё, что полезно показать врачу отдельно от предсказания модели:
- демография пациента / данные исследования / данные аппарата;
- структурированные измерения из WaveformAnnotationSequence (ЧСС, PR/QRS/QT,
  оси P/QRS/T, вольтажные критерии RV5/SV1/RV6/SV2 - это ГОТОВЫЕ компоненты
  критерия Sokolow-Lyon для гипертрофии ЛЖ, аппарат их уже посчитал!);
- текстовые заключения аппарата (UnformattedTextValue, напр. "Синусовый ритм...").

Не путать с dicom_signal.py: там - сырой waveform для модели, здесь - готовые
измерения/текст для UI, они читаются из разных секций DICOM независимо.
"""

import logging

import pydicom

logger = logging.getLogger(__name__)

_PATIENT_FIELDS = [
    "PatientID",
    "PatientName",
    "PatientSex",
    "PatientAge",
    "PatientBirthDate",
    "PatientSize",
    "PatientWeight",
    "EthnicGroup",
]
_STUDY_FIELDS = [
    "StudyInstanceUID",
    "StudyID",
    "StudyDate",
    "StudyTime",
    "StudyDescription",
    "AccessionNumber",
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "PhysiciansOfRecord",
]
_DEVICE_FIELDS = [
    "Manufacturer",
    "ManufacturerModelName",
    "DeviceSerialNumber",
    "StationName",
    "InstitutionName",
    "InstitutionalDepartmentName",
]

# Коды измерений SCPECG, которые прямо соответствуют вольтажным критериям
# гипертрофии ЛЖ (Sokolow-Lyon = SV1 + max(RV5, RV6); Cornell использует RaVL+SV3).
# Полезно явно пометить их во внешнем API, а не полагаться на то, что клиент
# сам вычленит нужные пункты из общего списка измерений.
VOLTAGE_CRITERIA_NAMES = {"RV5", "SV1", "RV6", "SV2", "RV5+SV1"}


def _get_str(ds, field: str) -> str | None:
    val = getattr(ds, field, None)
    return str(val) if val not in (None, "") else None


def _extract_demographics(ds) -> dict:
    def _collect(fields):
        return {f: v for f in fields if (v := _get_str(ds, f)) is not None}

    return {
        "patient": _collect(_PATIENT_FIELDS),
        "study": _collect(_STUDY_FIELDS),
        "device": _collect(_DEVICE_FIELDS),
    }


def _numeric_value(item) -> float | str | None:
    raw = getattr(item, "NumericValue", None)
    if raw is None or raw == "":
        return None
    # DS VR может прийти как MultiValue (список) - берём первое значение
    if hasattr(raw, "__iter__") and not isinstance(raw, str):
        raw = list(raw)[0] if len(raw) else None
        if raw is None:
            return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return str(raw)


def _extract_annotations(ds) -> dict:
    measurements = []
    text_annotations = []

    for item in getattr(ds, "WaveformAnnotationSequence", []):
        text = getattr(item, "UnformattedTextValue", None)
        if text:
            cleaned = str(text).strip()
            if cleaned:
                text_annotations.append(cleaned)
            continue

        value = _numeric_value(item)
        if value is None:
            continue

        name = None
        try:
            name = str(item.ConceptNameCodeSequence[0].CodeMeaning)
        except (AttributeError, IndexError):
            pass

        unit = None
        try:
            unit = str(item.MeasurementUnitsCodeSequence[0].CodeMeaning)
        except (AttributeError, IndexError):
            pass

        code = None
        try:
            code = str(item.ConceptNameCodeSequence[0].CodeValue)
        except (AttributeError, IndexError):
            pass

        measurements.append(
            {
                "name": name,
                "code": code,
                "value": value,
                "unit": unit,
                "is_voltage_criterion": (
                    name in VOLTAGE_CRITERIA_NAMES if name else False
                ),
            }
        )

    return {"measurements": measurements, "text_annotations": text_annotations}


def extract_metadata_from_dataset(ds: pydicom.Dataset) -> dict:
    metadata = _extract_demographics(ds)
    metadata.update(_extract_annotations(ds))
    return metadata


def extract_metadata_from_dicom_bytes(dicom_bytes: bytes) -> dict:
    import io

    try:
        ds = pydicom.dcmread(io.BytesIO(dicom_bytes))
    except pydicom.errors.InvalidDicomError as e:
        raise ValueError(f"Файл не является корректным DICOM: {e}") from e
    return extract_metadata_from_dataset(ds)
