"""
preprocessing.py

Единая точка препроцессинга сигнала для всех источников входа (DICOM, WFDB, .npy).

ВАЖНО: фильтрация/ресемплинг/нормализация переиспользуются напрямую из
train_utils.PTBXLMultiLabelDataset (те же статические методы, на которых
обучалась модель), а не дублируются здесь заново - любое случайное
расхождение между препроцессингом на трейне и на инференсе тихо роняет
качество модели без единой ошибки в логах.

Единственное, чего не было на трейне (там все записи PTB-XL - честные 10s),
но что обязательно для реального входа (DICOM с PACS может быть любой
длины) - явное приведение сигнала к фиксированной длительности ДО вызова
resample_to_length. Без этого шага resample_to_length интерпретирует
длительность входа как истинную и растягивает/сжимает частотный состав
сигнала под неё, что не соответствует данным, на которых модель обучалась.
"""

import numpy as np

from train_utils import PTBXLMultiLabelDataset
from core.config import settings, TARGET_LEN

CANONICAL_LEADS = [
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


def crop_or_pad_to_duration(
    signal: np.ndarray, fs_in: float, duration_sec: float
) -> np.ndarray:
    """Приводит [channels, N] к ровно duration_sec * fs_in отсчётам (центрированная обрезка/паддинг нулями)."""
    target_n = int(round(duration_sec * fs_in))
    n = signal.shape[1]
    if n == target_n:
        return signal
    if n > target_n:
        start = (n - target_n) // 2
        return signal[:, start : start + target_n]
    pad_total = target_n - n
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return np.pad(signal, ((0, 0), (pad_left, pad_right)), mode="constant")


def preprocess_raw_signal(signal: np.ndarray, fs_in: float) -> np.ndarray:
    """
    signal: [12, N] сырой сигнал в физических единицах (мВ), любая fs_in, любая длина.
    Возвращает: [12, TARGET_LEN] float32, готовый для подачи в модель.
    """
    if signal.shape[0] != 12:
        raise ValueError(f"Ожидалось 12 отведений, получено {signal.shape[0]}")

    signal = np.nan_to_num(signal.astype(np.float64), nan=0.0)

    # 1. Приводим к фиксированной длительности на РОДНОЙ частоте дискретизации -
    #    критично для корректности следующего шага (см. докстринг модуля).
    signal = crop_or_pad_to_duration(signal, fs_in, settings.TARGET_DURATION_SEC)

    # 2-4. Тот же порядок, что и на трейне: filter -> resample -> z-score
    signal = PTBXLMultiLabelDataset.filter_ecg(signal, fs_in)
    signal = PTBXLMultiLabelDataset.resample_to_length(signal, fs_in, TARGET_LEN)
    signal = PTBXLMultiLabelDataset.z_score_normalization(signal)

    return np.ascontiguousarray(signal, dtype=np.float32)


def reorder_leads(signal: np.ndarray, lead_names: list[str]) -> np.ndarray:
    """
    Переставляет отведения из lead_names (порядок, в котором они пришли) в
    CANONICAL_LEADS (порядок, в котором модель обучалась). Бросает ValueError,
    если каких-то из 12 стандартных отведений не хватает.
    """
    name_to_idx = {name.upper(): i for i, name in enumerate(lead_names)}
    missing = [l for l in CANONICAL_LEADS if l.upper() not in name_to_idx]
    if missing:
        raise ValueError(
            f"В сигнале не хватает отведений: {missing}. Найдены: {lead_names}"
        )
    idx = [name_to_idx[l.upper()] for l in CANONICAL_LEADS]
    return signal[idx, :]


def preprocess_for_display(signal: np.ndarray, fs_in: float) -> np.ndarray:
    """
    Тот же geometric pipeline, что и preprocess_raw_signal (crop/pad -> filter ->
    resample), НО БЕЗ z-score - для наложения теплокарты объяснимости на сигнал
    нужны физические единицы (мВ), а не обезличенные z-значения. Возвращает
    сигнал ТОЧНО в той же временной сетке (TARGET_LEN отсчётов), что и вход
    модели/CAM - координаты heatmap и графика совпадают 1:1 без доп. пересчёта.
    """
    if signal.shape[0] != 12:
        raise ValueError(f"Ожидалось 12 отведений, получено {signal.shape[0]}")

    signal = np.nan_to_num(signal.astype(np.float64), nan=0.0)
    signal = crop_or_pad_to_duration(signal, fs_in, settings.TARGET_DURATION_SEC)
    signal = PTBXLMultiLabelDataset.filter_ecg(signal, fs_in)
    signal = PTBXLMultiLabelDataset.resample_to_length(signal, fs_in, TARGET_LEN)

    return np.ascontiguousarray(signal, dtype=np.float32)
