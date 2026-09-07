"""
train_utils.py
Переиспользуемые компоненты для файнтюна ECGFounder на PTB-XL (multi-label).

Что здесь есть:
- set_seed                      -> воспроизводимость
- PTBXLMultiLabelDataset        -> Dataset с опциональным дисковым кэшем
                                    предобработанного сигнала (фильтрация
                                    детерминирована и не зависит от эпохи,
                                    поэтому пересчитывать её каждый раз -
                                    расточительно)
- load_ecgfounder                -> загрузка претрейн-весов ECGFounder
                                    (12-lead / 1-lead), с фиксом под torch>=2.6
- fast_eval                      -> быстрая эпохальная валидация
                                    (AUROC/AUPRC/Precision/Recall/F1/Specificity
                                    при фиксированном пороге, без bootstrap)
- full_eval_with_ci               -> полная оценка (для финального теста):
                                    подбор порога по balanced accuracy +
                                    bootstrap 95% CI для всех метрик
- EarlyStopper, save_run_config  -> сервисные функции
"""

import os
import json
import random
import warnings

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset
from scipy.signal import butter, filtfilt, iirnotch
from scipy.interpolate import interp1d
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    balanced_accuracy_score,
)
from sklearn.exceptions import UndefinedMetricWarning
import wfdb

# На малых батчах/редких классах sklearn закономерно предупреждает об
# отсутствии одного из классов (AUROC/precision/recall не определены) —
# это ожидаемо для multi-label с редкими диагнозами, а не ошибка. NaN в
# результатах в этих случаях - осознанный сигнал "метрика неопределена
# на этом классе/фолде", а не баг.
warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
warnings.filterwarnings(
    "ignore", message="A single label was found in 'y_true' and 'y_pred'"
)
warnings.filterwarnings("ignore", message="No positive class found in y_true")
warnings.filterwarnings("ignore", category=UndefinedMetricWarning)


# ----------------------------------------------------------------------
# Reproducibility
# ----------------------------------------------------------------------
def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# ----------------------------------------------------------------------
# Dataset
# ----------------------------------------------------------------------
class PTBXLMultiLabelDataset(Dataset):
    """
    Multi-label датасет для PTB-XL (или любого набора с multi-hot метками).

    Отличия от исходного варианта из ноутбука:
    - порядок обработки исправлен: filter -> resample -> z-score
      (нормализация должна применяться к финальному сигналу, который
      реально видит модель, а не к сигналу до ресемплинга);
    - resample - это honest no-op, если сигнал уже нужной длины
      (для filename_hr это почти всегда так: 500 Hz * 10s = 5000 отсчётов),
      что экономит существенную часть CPU-времени на каждый epoch;
    - опциональное дисковое кэширование (cache_dir): предобработка
      детерминирована, поэтому кэш существенно ускоряет 2+ эпоху обучения.
    """

    def __init__(
        self,
        ecg_path,
        df,
        label_cols,
        fs_signal=500,
        target_len=5000,
        cache_dir=None,
        filename_col="filename",
    ):
        self.df = df.reset_index(drop=True)
        self.ecg_path = ecg_path
        self.label_cols = list(label_cols)
        self.fs_signal = fs_signal
        self.target_len = target_len
        self.cache_dir = cache_dir
        self.filename_col = filename_col
        if cache_dir is not None:
            os.makedirs(cache_dir, exist_ok=True)

    def __len__(self):
        return len(self.df)

    @staticmethod
    def z_score_normalization(signal):
        return (signal - np.mean(signal)) / (np.std(signal) + 1e-8)

    @staticmethod
    def resample_to_length(ts, fs_in, target_len):
        n = ts.shape[1]
        if n == target_len:
            return ts
        t = n / fs_in
        x_old = np.linspace(0, t, num=n, endpoint=True)
        x_new = np.linspace(0, t, num=target_len, endpoint=True)
        out = np.zeros((ts.shape[0], target_len), dtype=ts.dtype)
        for i in range(ts.shape[0]):
            f = interp1d(x_old, ts[i, :], kind="linear")
            out[i, :] = f(x_new)
        return out

    @staticmethod
    def filter_ecg(data, fs):
        """High-pass 1Hz -> low-pass 30Hz (Butterworth, 2nd order) -> notch 50Hz."""
        b_hp, a_hp = butter(2, 1 / (fs / 2), btype="highpass")
        data = filtfilt(b_hp, a_hp, data, axis=1)

        b_lp, a_lp = butter(2, 30 / (fs / 2), btype="lowpass")
        data = filtfilt(b_lp, a_lp, data, axis=1)

        b_notch, a_notch = iirnotch(50, Q=30, fs=fs)
        data = filtfilt(b_notch, a_notch, data, axis=1)
        return data

    def _load_raw(self, file_path):
        sig, _meta = wfdb.rdsamp(self.ecg_path + file_path)
        sig = np.nan_to_num(np.asarray(sig), nan=0.0)
        sig = np.transpose(sig, (1, 0))  # -> [channels, N]
        return sig

    def _process(self, file_path):
        cache_path = None
        if self.cache_dir is not None:
            safe_name = file_path.replace("/", "_").replace("\\", "_")
            cache_path = os.path.join(self.cache_dir, safe_name + ".npy")
            if os.path.exists(cache_path):
                return np.load(cache_path)

        data = self._load_raw(file_path)
        data = self.filter_ecg(data, self.fs_signal)
        data = self.resample_to_length(data, self.fs_signal, self.target_len)
        data = self.z_score_normalization(data)
        data = np.ascontiguousarray(data, dtype=np.float32)

        if cache_path is not None:
            np.save(cache_path, data)
        return data

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        file_path = str(row[self.filename_col])
        label = row[self.label_cols].to_numpy(dtype=np.float32)
        signal = self._process(file_path)
        return torch.from_numpy(signal), torch.from_numpy(label)


# ----------------------------------------------------------------------
# Model loading
# ----------------------------------------------------------------------
def load_ecgfounder(
    device, checkpoint_path, n_classes, in_channels=12, linear_prob=False
):
    """
    Загружает претрейн ECGFounder и заменяет последний слой под n_classes.

    Фиксы относительно оригинального finetune_model.py:
    - weights_only=False (torch>=2.6 иначе бросает исключение на этом чекпоинте,
      т.к. в нём сохранены не только тензоры);
    - поддержка чекпоинта как {'state_dict': ...}, так и голого state_dict.
    """
    from net1d import Net1D

    model = Net1D(
        in_channels=in_channels,
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
        n_classes=n_classes,
    )

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    state_dict = (
        checkpoint["state_dict"]
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint
        else checkpoint
    )
    state_dict = {k: v for k, v in state_dict.items() if not k.startswith("dense.")}

    missing = model.load_state_dict(state_dict, strict=False)

    model.dense = nn.Linear(model.dense.in_features, n_classes).to(device)

    if linear_prob:
        for name, p in model.named_parameters():
            if "dense" not in name:
                p.requires_grad = False

    model.to(device)
    return model, missing


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------
def _binary_counts(gt_int, pred_labels):
    tn, fp, fn, tp = confusion_matrix(gt_int, pred_labels, labels=[0, 1]).ravel()
    return tn, fp, fn, tp


def fast_eval(gt, pred, threshold=0.5, class_names=None):
    """
    Дешёвая метрика для мониторинга КАЖДОЙ эпохи (без bootstrap):
    AUROC, AUPRC, Precision, Recall, F1, Specificity при фиксированном пороге.

    Возвращает (means_dict, per_class_df).
    """
    n_task = gt.shape[1]
    names = class_names or [f"class_{i}" for i in range(n_task)]
    rows = {}
    for i in range(n_task):
        g = np.nan_to_num(gt[:, i], nan=0)
        p = np.nan_to_num(pred[:, i], nan=0)

        try:
            auroc = roc_auc_score(g, p)
        except ValueError:
            auroc = float("nan")
        try:
            auprc = average_precision_score(g, p)
        except ValueError:
            auprc = float("nan")

        pl = (p >= threshold).astype(int)
        tn, fp, fn, tp = _binary_counts(g.astype(int), pl)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        rows[names[i]] = dict(
            AUROC=auroc,
            AUPRC=auprc,
            Precision=precision,
            Recall=recall,
            Specificity=specificity,
            F1=f1,
        )

    df = pd.DataFrame(rows).T
    means = df.mean(numeric_only=True, skipna=True).to_dict()
    return means, df


def find_optimal_thresholds(gt, pred, grid=None):
    """Порог на класс, максимизирующий balanced accuracy (как в ptbxl_eval.py)."""
    grid = grid if grid is not None else np.linspace(0.05, 0.95, 19)
    n_task = gt.shape[1]
    best = []
    for i in range(n_task):
        g = gt[:, i]
        best_ba, best_t = -1.0, 0.5
        for t in grid:
            pl = (pred[:, i] >= t).astype(int)
            ba = balanced_accuracy_score(g, pl)
            if ba > best_ba:
                best_ba, best_t = ba, t
        best.append(best_t)
    return best


def find_thresholds_joint_sens_spec(
    gt, pred, class_names=None, target_sens=0.80, target_spec=0.80, grid_size=399
):
    """
    Подбирает порог на класс, максимизируя min(sensitivity, specificity) —
    НЕ их среднее (в отличие от balanced accuracy / find_optimal_thresholds).

    Почему это отдельная функция:
    Требование вида "sensitivity >= X И specificity >= X по каждому классу
    отдельно" - это не то же самое, что максимизация balanced accuracy
    ((sens+spec)/2) или Youden's J (sens+spec-1). Средняя точка может легко
    давать высокий sens за счёт низкого spec (или наоборот), проходя мимо
    требования "обе >= X" даже когда такая точка на ROC-кривой существует.
    max(min(sens, spec)) - это ровно та целевая функция, которая ищет
    порог, наиболее соответствующий требованию "обе метрики одновременно
    как можно выше", и на мелкой сетке (399 точек вместо 19) находит
    точки, которые грубый перебор balanced accuracy пропускает.

    Возвращает DataFrame с порогом, достигнутыми sens/spec и флагом,
    выполняется ли условие target_sens/target_spec.
    """
    n_task = gt.shape[1]
    names = class_names or [f"class_{i}" for i in range(n_task)]
    grid = np.linspace(0.01, 0.99, grid_size)

    rows = []
    for i in range(n_task):
        g = np.nan_to_num(gt[:, i], nan=0).astype(int)
        p = np.nan_to_num(pred[:, i], nan=0)

        best_min, best_t, best_sens, best_spec = -1.0, 0.5, 0.0, 0.0
        for t in grid:
            pl = (p >= t).astype(int)
            tn, fp, fn, tp = _binary_counts(g, pl)
            sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            score = min(sens, spec)
            if score > best_min:
                best_min, best_t, best_sens, best_spec = score, t, sens, spec

        rows.append(
            dict(
                Label=names[i],
                Threshold=round(float(best_t), 4),
                Sensitivity=round(best_sens, 4),
                Specificity=round(best_spec, 4),
                meets_target=bool(
                    best_sens >= target_sens and best_spec >= target_spec
                ),
            )
        )

    return pd.DataFrame(rows)


def _bootstrap_ci(g, p, metric_fn, n_bootstrap=1000, ci=95, seed=0):
    rng = np.random.default_rng(seed)
    n = len(g)
    vals = np.empty(n_bootstrap)
    for b in range(n_bootstrap):
        idx = rng.integers(0, n, n)
        try:
            vals[b] = metric_fn(g[idx], p[idx])
        except Exception:
            vals[b] = np.nan
    lo = np.nanpercentile(vals, (100 - ci) / 2)
    hi = np.nanpercentile(vals, 100 - (100 - ci) / 2)
    return float(lo), float(hi)


def full_eval_with_ci(
    gt,
    pred,
    class_names=None,
    thresholds="dynamic",
    n_bootstrap=1000,
    ci=95,
    seed=0,
    target_sens=0.80,
    target_spec=0.80,
):
    """
    Полная оценка (запускать один раз на тесте, не на каждой эпохе):
    AUROC, AUPRC, Precision, Recall, Specificity, F1 + bootstrap 95% CI
    для каждого класса.

    thresholds:
      'dynamic'         -> порог максимизирует balanced accuracy (грубая сетка, 19 точек)
      'sens_spec_joint' -> порог максимизирует min(sensitivity, specificity) на мелкой
                           сетке (399 точек). Используйте этот режим, если требование -
                           "sensitivity >= X И specificity >= X по каждому классу
                           отдельно", т.к. это НЕ то же самое, что максимизация их
                           среднего (balanced accuracy) - см. find_thresholds_joint_sens_spec.
      0.5 | список       -> фиксированный порог(и)
    """
    n_task = gt.shape[1]
    names = class_names or [f"class_{i}" for i in range(n_task)]

    if thresholds == "dynamic":
        ths = find_optimal_thresholds(gt, pred)
    elif thresholds == "sens_spec_joint":
        joint_df = find_thresholds_joint_sens_spec(
            gt,
            pred,
            class_names=names,
            target_sens=target_sens,
            target_spec=target_spec,
        )
        ths = joint_df["Threshold"].tolist()
    elif thresholds is None or thresholds == 0.5:
        ths = [0.5] * n_task
    else:
        ths = list(thresholds)

    records = []
    for i in range(n_task):
        g = np.nan_to_num(gt[:, i], nan=0).astype(int)
        p = np.nan_to_num(pred[:, i], nan=0)
        t = float(ths[i])

        def _prec(gg, pp, thr=t):
            pll = (pp >= thr).astype(int)
            tp_ = np.sum((gg == 1) & (pll == 1))
            fp_ = np.sum((gg == 0) & (pll == 1))
            return tp_ / (tp_ + fp_) if (tp_ + fp_) > 0 else 0.0

        def _rec(gg, pp, thr=t):
            pll = (pp >= thr).astype(int)
            tp_ = np.sum((gg == 1) & (pll == 1))
            fn_ = np.sum((gg == 1) & (pll == 0))
            return tp_ / (tp_ + fn_) if (tp_ + fn_) > 0 else 0.0

        def _spec(gg, pp, thr=t):
            pll = (pp >= thr).astype(int)
            tn_ = np.sum((gg == 0) & (pll == 0))
            fp_ = np.sum((gg == 0) & (pll == 1))
            return tn_ / (tn_ + fp_) if (tn_ + fp_) > 0 else 0.0

        def _f1(gg, pp, thr=t):
            pr = _prec(gg, pp, thr)
            rc = _rec(gg, pp, thr)
            return 2 * pr * rc / (pr + rc) if (pr + rc) > 0 else 0.0

        def _auroc(gg, pp):
            try:
                return roc_auc_score(gg, pp)
            except ValueError:
                return np.nan

        def _auprc(gg, pp):
            try:
                return average_precision_score(gg, pp)
            except ValueError:
                return np.nan

        precision, recall = _prec(g, p), _rec(g, p)
        specificity, f1 = _spec(g, p), _f1(g, p)
        auroc, auprc = _auroc(g, p), _auprc(g, p)

        auroc_ci = _bootstrap_ci(g, p, _auroc, n_bootstrap, ci, seed + i)
        auprc_ci = _bootstrap_ci(g, p, _auprc, n_bootstrap, ci, seed + i + 1000)
        prec_ci = _bootstrap_ci(g, p, _prec, n_bootstrap, ci, seed + i + 2000)
        rec_ci = _bootstrap_ci(g, p, _rec, n_bootstrap, ci, seed + i + 3000)
        spec_ci = _bootstrap_ci(g, p, _spec, n_bootstrap, ci, seed + i + 4000)
        f1_ci = _bootstrap_ci(g, p, _f1, n_bootstrap, ci, seed + i + 5000)

        records.append(
            dict(
                Label=names[i],
                Threshold=round(t, 3),
                AUROC=round(auroc, 4),
                AUROC_CI=tuple(round(v, 4) for v in auroc_ci),
                AUPRC=round(auprc, 4),
                AUPRC_CI=tuple(round(v, 4) for v in auprc_ci),
                Precision=round(precision, 4),
                Precision_CI=tuple(round(v, 4) for v in prec_ci),
                Recall=round(recall, 4),
                Recall_CI=tuple(round(v, 4) for v in rec_ci),
                Specificity=round(specificity, 4),
                Specificity_CI=tuple(round(v, 4) for v in spec_ci),
                F1=round(f1, 4),
                F1_CI=tuple(round(v, 4) for v in f1_ci),
                n_pos=int(g.sum()),
                n_neg=int(len(g) - g.sum()),
            )
        )

    return pd.DataFrame(records)


# ----------------------------------------------------------------------
# Misc
# ----------------------------------------------------------------------
class EarlyStopper:
    def __init__(self, patience=5, mode="max", min_delta=1e-4):
        self.patience = patience
        self.mode = mode
        self.min_delta = min_delta
        self.best = None
        self.counter = 0
        self.should_stop = False

    def step(self, value):
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return
        if self.best is None:
            self.best = value
            return
        improved = (
            (value > self.best + self.min_delta)
            if self.mode == "max"
            else (value < self.best - self.min_delta)
        )
        if improved:
            self.best = value
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True


def save_run_config(cfg, run_dir):
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump(cfg, f, indent=2, default=str, ensure_ascii=False)
