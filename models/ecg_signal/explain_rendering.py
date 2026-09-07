"""
explain_rendering.py

Рендерит объяснение (combined-карта из explainability.py) как PNG: 12 отведений
в сетке 6x2, поверх каждого - полупрозрачная теплокарта важности по этому
отведению. signal_mV должен быть В ТОЙ ЖЕ временной сетке, что и combined-карта
(см. preprocessing.preprocess_for_display - тот же crop/filter/resample, но без
z-score, чтобы амплитуда была в физических единицах, а не обезличенной).
"""

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _enhance_for_display(
    row: np.ndarray, low_percentile: float = 50.0, gamma: float = 0.4
) -> np.ndarray:
    """
    Контрастная растяжка ДЛЯ ОТОБРАЖЕНИЯ (не меняет числовой контракт API - только
    визуал). Сырая combined-карта сильно смещена к нулю (много точек около 0,
    редкие пики около 1) - линейная 0..1 нормализация делает почти всю карту
    почти прозрачной, виден только пик. Обрезаем нижние low_percentile% в 0
    (они и так малозначимы), тянем остаток на 0..1, затем гамма<1 дополнительно
    поднимает средние значения - совместно это даёт заметный цвет уже на
    умеренно важных участках, а не только на самом ярком пике.
    Считается ОТДЕЛЬНО НА КАЖДОЕ ОТВЕДЕНИЕ (не глобально) - иначе отведения
    со слабым сигналом визуально теряются на фоне самого яркого отведения.
    """
    lo = np.percentile(row, low_percentile)
    hi = row.max()
    stretched = np.clip((row - lo) / (hi - lo + 1e-8), 0, 1)
    return stretched**gamma


def render_explanation_png(
    signal_mV: np.ndarray,
    fs: float,
    lead_names: list[str],
    combined_map: np.ndarray,
    class_name: str,
    probability: float,
) -> bytes:
    """
    signal_mV: [12, N] мВ.
    combined_map: [12, N] в [0, 1] (см. explainability.combine_maps).
    """
    n_leads, n = signal_mV.shape
    t = np.arange(n) / fs

    fig, axes = plt.subplots(6, 2, figsize=(15, 12), sharex=True)
    fig.suptitle(
        f"{class_name} (p={probability:.2f}) - объяснение: Grad-CAM++ x Integrated Gradients",
        fontsize=12,
    )

    for i, ax in enumerate(axes.flatten()):
        if i >= n_leads:
            ax.axis("off")
            continue

        y_min, y_max = float(signal_mV[i].min()), float(signal_mV[i].max())
        pad = 0.1 * (y_max - y_min + 1e-6)

        heat = _enhance_for_display(combined_map[i])[None, :]
        ax.imshow(
            heat,
            extent=[t[0], t[-1], y_min - pad, y_max + pad],
            aspect="auto",
            cmap="YlOrRd",
            alpha=0.85,
            origin="lower",
            vmin=0,
            vmax=1,
        )
        ax.plot(t, signal_mV[i], color="black", linewidth=0.8)
        ax.set_title(lead_names[i], loc="left", fontsize=9)
        ax.set_ylim(y_min - pad, y_max + pad)
        ax.set_yticks([])
        ax.grid(which="both", color="grey", linestyle="-", linewidth=0.2, alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
