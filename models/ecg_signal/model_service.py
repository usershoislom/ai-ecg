"""
model_service.py

Загружает дообученную ECGFounder (Net1D, 5 классов PTB-XL) и веса-пороги на класс,
подобранные в ноутбуке через find_thresholds_joint_sens_spec (или find_optimal_thresholds).

ВАЖНО: в отличие от загрузки ИСХОДНОГО претрейна ECGFounder (см. tu.load_ecgfounder,
которая срезает dense.* и грузит strict=False, потому что размер выходного слоя
меняется 150->5), здесь чекпоинт УЖЕ дообучен под 5 классов - грузим state_dict
целиком, strict=True. Использование tu.load_ecgfounder тут было бы ошибкой:
она снова обрежет/заменит dense-слой и вы получите случайную инициализацию головы
вместо дообученных весов.
"""

import json
import logging
import threading

import numpy as np
import torch

from core.config import settings
from models.ecg_signal.net1d import Net1D

logger = logging.getLogger(__name__)


class ModelService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.device = torch.device(
            settings.DEVICE
            if torch.cuda.is_available() or settings.DEVICE == "cpu"
            else "cpu"
        )
        self.class_names = settings.SUPERCLASSES
        self.model = self._build_and_load_model()
        self.thresholds = self._load_thresholds()
        logger.info(
            "Model loaded on %s, classes=%s, thresholds=%s",
            self.device,
            self.class_names,
            self.thresholds,
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
            n_classes=len(self.class_names),
        )
        checkpoint = torch.load(
            settings.MODEL_SIGNAL_PATH, map_location=self.device, weights_only=False
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

    def _load_thresholds(self) -> dict:
        try:
            with open(settings.THRESHOLDS_SIGNAL_PATH) as f:
                raw = json.load(f)
            return {c: float(raw.get(c, 0.5)) for c in self.class_names}
        except FileNotFoundError:
            logger.warning(
                "Файл порогов %s не найден - используется 0.5 для всех классов",
                settings.THRESHOLDS_SIGNAL_PATH,
            )
            return {c: 0.5 for c in self.class_names}

    @torch.no_grad()
    def predict(self, signal: np.ndarray) -> list[dict]:
        """
        signal: [12, TARGET_LEN] float32, уже препроцессенный (preprocessing.preprocess_raw_signal).
        Возвращает список dict per class: label, probability, threshold, positive.
        """
        x = torch.from_numpy(signal).unsqueeze(0).to(self.device)  # [1, 12, N]
        logits = self.model(x)
        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()

        results = []
        for i, name in enumerate(self.class_names):
            thr = self.thresholds[name]
            prob = float(probs[i])
            results.append(
                dict(label=name, probability=prob, threshold=thr, positive=prob >= thr)
            )
        return results

    @classmethod
    def get_instance(cls) -> "ModelService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
