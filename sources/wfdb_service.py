"""
wfdb_service.py

Извлечение сигнала из WFDB-записи (.hea/.dat), как в PTB-XL, для внутреннего
пайплайна предсказания (тестирование/валидация на WFDB-датасетах, не для
пользовательской загрузки файлов - см. ответ пользователя: юзерам только DICOM).
"""

import os

import numpy as np
import wfdb

from core.config import settings
from models.ecg_signal.preprocessing import CANONICAL_LEADS, reorder_leads

# Стандартный порядок отведений в PTB-XL WFDB-записях (см. dataset.py оригинального репо)
_PTBXL_WFDB_LEAD_ORDER = [
    "I",
    "II",
    "III",
    "aVR",
    "aVF",
    "aVL",
    "V1",
    "V2",
    "V3",
    "V4",
    "V5",
    "V6",
]


def extract_signal_from_wfdb(record_name: str):
    """
    record_name: относительный путь без расширения (напр. 'records500/00000/00001_hr'),
    ищется внутри settings.WFDB_ROOT.
    Возвращает (signal[12, N], fs).
    """
    full_path = os.path.join(settings.WFDB_ROOT, record_name)
    hea_path = full_path + ".hea"
    if not os.path.exists(hea_path):
        raise FileNotFoundError(f"WFDB-запись не найдена: {hea_path}")

    sig, meta = wfdb.rdsamp(full_path)
    fs = float(meta["fs"])
    sig_names = meta.get("sig_name", _PTBXL_WFDB_LEAD_ORDER)

    signal = np.nan_to_num(np.asarray(sig), nan=0.0).T  # [C, N]
    signal = reorder_leads(signal, sig_names)
    return signal, fs
