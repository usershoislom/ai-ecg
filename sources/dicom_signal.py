"""
dicom_signal.py

Извлечение СЫРОГО сигнала ЭКГ (не картинки!) из DICOM Waveform IE.

Отличия от старого dicom_converter.py:
- имена отведений читаются из ChannelDefinitionSequence / ChannelSourceSequence,
  а не предполагается фиксированный порядок I,II,III,aVR,aVL,aVF,V1..V6 -
  на реальных PACS-архивах порядок каналов не гарантирован;
- частота дискретизации читается из тега SamplingFrequency, а не хардкодится;
- применяются ChannelSensitivity/ChannelBaseline для перевода из "сырых"
  digital units в физические (мВ) - без этого разные записи могут иметь
  разный масштаб не только из-за физиологии, но и из-за настроек аппарата.
"""

import io
import logging
from dataclasses import dataclass

import numpy as np
import pydicom

logger = logging.getLogger(__name__)

# Соответствие стандартных DICOM CodeMeaning (SCPECG/MDC) -> каноническое имя отведения.
# DICOM обычно даёt что-то вроде "Lead I", "Lead II", "Lead V1" и т.п. в CodeMeaning
# ChannelSourceSequence. Список расширяем по мере встречи новых вариантов написания.
_LEAD_NAME_MAP = {
    "I": "I",
    "LEAD I": "I",
    "LEAD I (EINTHOVEN)": "I",
    "II": "II",
    "LEAD II": "II",
    "LEAD II (EINTHOVEN)": "II",
    "III": "III",
    "LEAD III": "III",
    "LEAD III (EINTHOVEN)": "III",
    "AVR": "aVR",
    "LEAD AVR": "aVR",
    "LEAD AVR (GOLDBERGER)": "aVR",
    "AVL": "aVL",
    "LEAD AVL": "aVL",
    "LEAD AVL (GOLDBERGER)": "aVL",
    "AVF": "aVF",
    "LEAD AVF": "aVF",
    "LEAD AVF (GOLDBERGER)": "aVF",
    "V1": "V1",
    "LEAD V1": "V1",
    "V2": "V2",
    "LEAD V2": "V2",
    "V3": "V3",
    "LEAD V3": "V3",
    "V4": "V4",
    "LEAD V4": "V4",
    "V5": "V5",
    "LEAD V5": "V5",
    "V6": "V6",
    "LEAD V6": "V6",
}

# Множитель для перевода в мВ (канонические физ. единицы пайплайна). Смотрим и на
# CodeValue, и на CodeMeaning, т.к. разные аппараты заполняют по-разному.
_UNIT_TO_MV = {
    "UV": 0.001,
    "MICROVOLT": 0.001,
    "MV": 1.0,
    "MILLIVOLT": 1.0,
    "V": 1000.0,
    "VOLT": 1000.0,
}


@dataclass
class ExtractedSignal:
    signal: np.ndarray  # [n_channels, n_samples], физические единицы (мВ)
    lead_names: list[str]  # имена каналов в исходном порядке signal
    fs: float  # Гц


def _resolve_lead_name(channel_item, fallback_idx: int) -> str:
    """Пытается достать читаемое имя отведения из ChannelSourceSequence; иначе - позиционный fallback."""
    try:
        src_seq = channel_item.ChannelSourceSequence
        for src in src_seq:
            meaning = str(getattr(src, "CodeMeaning", "")).strip().upper()
            if meaning in _LEAD_NAME_MAP:
                return _LEAD_NAME_MAP[meaning]
    except (AttributeError, IndexError):
        pass
    return f"UNKNOWN_{fallback_idx}"


def _channel_unit_to_mv_factor(channel_item, fallback_idx: int) -> float:
    """
    Определяет множитель перевода в мВ по ChannelSensitivityUnitsSequence.
    Если тег отсутствует/не распознан - логируем warning и предполагаем микровольты
    (типичное сырое АЦП-разрешение для ЭКГ-усилителей), а не молча считаем мВ:
    ошибочное предположение "уже в мВ" даёт 1000-кратную ошибку амплитуды.
    """
    try:
        units_seq = channel_item.ChannelSensitivityUnitsSequence
        for u in units_seq:
            code = str(getattr(u, "CodeValue", "")).strip().upper()
            meaning = str(getattr(u, "CodeMeaning", "")).strip().upper()
            for key in (code, meaning):
                if key in _UNIT_TO_MV:
                    return _UNIT_TO_MV[key]
    except (AttributeError, IndexError):
        pass
    logger.warning(
        "Канал %d: ChannelSensitivityUnitsSequence не найден/не распознан - "
        "предполагаем микровольты (типичное сырое АЦП-разрешение ЭКГ)",
        fallback_idx,
    )
    return _UNIT_TO_MV["UV"]


def _channel_gain_baseline(channel_item, fallback_idx: int):
    """
    Возвращает (gain_mV, baseline_mV) для перевода: physical_mV = raw * gain_mV + baseline_mV.

    По DICOM PS3.3 C.10.9 (Channel Baseline): "Offset of encoded sample value 0
    from actual 0, using the units defined in Channel Sensitivity Units Sequence" -
    то есть baseline УЖЕ в физических единицах и прибавляется ПОСЛЕ масштабирования,
    а не вычитается из сырого отсчёта до него. Раньше здесь было (raw - baseline)*gain,
    что математически некорректно (хоть и не влияло на классификатор из-за z-score,
    см. preprocessing - z-score гасит любую глобальную аддитивную/мультипликативную
    константу, если она одинакова по всем каналам). Для метаданных/абсолютных
    значений (например, вывод RV5/SV1 врачу) это уже важно считать правильно.
    """
    unit_factor = _channel_unit_to_mv_factor(channel_item, fallback_idx)
    sensitivity = float(getattr(channel_item, "ChannelSensitivity", 1.0) or 1.0)
    correction = float(
        getattr(channel_item, "ChannelSensitivityCorrectionFactor", 1.0) or 1.0
    )
    baseline_raw_units = float(getattr(channel_item, "ChannelBaseline", 0.0) or 0.0)

    gain_mV = sensitivity * correction * unit_factor
    baseline_mV = baseline_raw_units * unit_factor
    return gain_mV, baseline_mV


def extract_signal_from_dicom_bytes(dicom_bytes: bytes) -> ExtractedSignal:
    try:
        ds = pydicom.dcmread(io.BytesIO(dicom_bytes))
    except pydicom.errors.InvalidDicomError as e:
        raise ValueError(f"Файл не является корректным DICOM: {e}") from e
    return extract_signal_from_dataset(ds)


def extract_signal_from_dataset(ds: pydicom.Dataset) -> ExtractedSignal:
    if not hasattr(ds, "WaveformSequence") or len(ds.WaveformSequence) == 0:
        raise ValueError("В DICOM нет WaveformSequence - это не ЭКГ-waveform запись")

    waveform_item = ds.WaveformSequence[0]

    num_channels = int(waveform_item.NumberOfWaveformChannels)
    num_samples = int(waveform_item.NumberOfWaveformSamples)
    fs = float(waveform_item.SamplingFrequency)

    bits_allocated = int(getattr(waveform_item, "WaveformBitsAllocated", 16))
    sample_interpretation = str(
        getattr(waveform_item, "WaveformSampleInterpretation", "SS")
    )
    dtype_map = {
        ("SS", 16): np.int16,
        ("US", 16): np.uint16,
        ("SS", 8): np.int8,
        ("US", 8): np.uint8,
        ("SS", 32): np.int32,
        ("US", 32): np.uint32,
    }
    dt = dtype_map.get((sample_interpretation, bits_allocated), np.int16)

    raw = np.frombuffer(waveform_item.WaveformData, dtype=dt)
    raw = raw.reshape(num_samples, num_channels).astype(np.float64)  # [N, C]

    channel_defs = list(getattr(waveform_item, "ChannelDefinitionSequence", []))
    lead_names = []
    physical = np.zeros_like(raw)
    for c in range(num_channels):
        if c < len(channel_defs):
            name = _resolve_lead_name(channel_defs[c], c)
            gain_mV, baseline_mV = _channel_gain_baseline(channel_defs[c], c)
        else:
            name = f"UNKNOWN_{c}"
            gain_mV, baseline_mV = (
                0.001,
                0.0,
            )  # без метаданных - fallback: считаем сырые отсчёты микровольтами
        lead_names.append(name)
        physical[:, c] = raw[:, c] * gain_mV + baseline_mV

    signal = physical.T  # -> [C, N]
    return ExtractedSignal(signal=signal, lead_names=lead_names, fs=fs)
