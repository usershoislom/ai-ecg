"""
model_service_raw150.py

Отдельный сервис для ИСХОДНОЙ (не дообученной) ECGFounder - 150 диагностических
классов из претрейна.

Отличия от model_service.py (5 классов, дообученная голова, откалиброванные пороги):
- чекпоинт грузится ЦЕЛИКОМ как есть (strict=True), БЕЗ обрезки/замены
  dense-слоя - это тот же файл, что MODEL_PATH был ДО файнтюна (checkpoint_12lead
  в CONFIG ноутбука);
- нет откалиброванных порогов на класс (в отличие от 5-классовой модели, где
  пороги подбирались через find_thresholds_joint_sens_spec) - поэтому здесь
  возвращаются сырые вероятности, а не positive/negative;
- имена классов читаются из tasks.txt (см. ptbxl_eval.py авторов ECGFounder,
  by одному названию на строку) - если файла нет, используются обобщённые
  имена class_0..class_149, и в лог пишется предупреждение.
"""

import logging
import os
import threading

import numpy as np
import torch

from core.config import settings
from models.ecg_signal.net1d import Net1D

logger = logging.getLogger(__name__)


def _load_class_names(path: str, n_classes: int) -> list[str]:
    if os.path.exists(path):
        with open(path) as f:
            names = [line.strip() for line in f if line.strip()]
        if len(names) == n_classes:
            return names
        logger.warning(
            "Файл имён классов %s содержит %d строк, ожидалось %d - "
            "используются обобщённые имена class_i",
            path,
            len(names),
            n_classes,
        )
    else:
        logger.warning(
            "Файл имён классов %s не найден - используются обобщённые имена class_i. "
            "Положите tasks.txt из репозитория ECGFounder (по одному имени класса на строку).",
            path,
        )
    return [f"class_{i}" for i in range(n_classes)]


class RawECGFounderService:
    """Синглтон: исходная ECGFounder на 150 классов (грузится отдельно от дообученной)."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.device = torch.device(
            settings.DEVICE
            if torch.cuda.is_available() or settings.DEVICE == "cpu"
            else "cpu"
        )
        self.n_classes = settings.NUM_CLASSES_150
        self.class_names = _load_class_names(
            settings.CLASS_NAMES_150_PATH, self.n_classes
        )
        self.model = self._build_and_load_model()
        logger.info(
            "Исходная ECGFounder (%d классов) загружена на %s",
            self.n_classes,
            self.device,
        )

    def _build_and_load_model(self) -> torch.nn.Module:
        model = Net1D(
            in_channels=settings.NUM_LEAD,
            base_filters=64,
            ratio=1,
            filter_list=[64, 160, 160, 400, 400, 1024, 1024],
            m_blocks_list=[2, 2, 2, 3, 3, 4, 4],
            kernel_size=16,
            stride=2,
            groups_width=16,
            verbose=False,
            use_bn=False,
            use_do=False,
            n_classes=self.n_classes,
        )
        checkpoint = torch.load(
            settings.MODEL_150_PATH, map_location=self.device, weights_only=False
        )
        state_dict = (
            checkpoint["state_dict"]
            if isinstance(checkpoint, dict) and "state_dict" in checkpoint
            else checkpoint
        )
        model.load_state_dict(state_dict, strict=True)
        model.to(self.device)
        model.eval()
        return model

    @torch.no_grad()
    def predict(self, signal: np.ndarray) -> list[dict]:
        """signal: [12, TARGET_LEN] float32, уже препроцессенный. Возвращает [{label, probability}] x 150."""
        x = torch.from_numpy(signal).unsqueeze(0).to(self.device)
        logits = self.model(x)
        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()
        return [
            dict(label=name, probability=float(p))
            for name, p in zip(self.class_names, probs)
        ]

    @classmethod
    def get_instance(cls) -> "RawECGFounderService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
