"""
explainability.py

Объяснимость предсказаний Net1D (5-классовая дообученная ECGFounder):
- GradCAMPlusPlus: класс-специфичная временная карта важности с последнего
  предпоследнего conv-стейджа (stage_list[-2] - компромисс между семантической
  глубиной и временным разрешением, см. обсуждение: последний стейдж даёт
  1 CAM-отсчёт = 500мс, предпоследний - 250мс, тот же канальный охват 1024).
  Одна карта на ВСЕ 12 отведений сразу - архитектурное ограничение: первая же
  свёртка (first_conv, groups=1) смешивает все 12 каналов, дальше в сети уже
  нет оси "отведение".
- integrated_gradients: attribution на СЫРОМ входе [12, N] (до first_conv) -
  единственный из двух методов, что даёт разбивку ИМЕННО по отведениям.
- combine_maps: поэлементное произведение нормализованных |IG| и Grad-CAM++ -
  подсвечивает время+отведение, где сходятся оба метода (меньше шума, чем
  любой метод по отдельности).

Оба метода запускаются на logit'е (ДО sigmoid) конкретного класса - это и есть
"class-specific" часть Grad-CAM/IG, поэтому для multi-label с 5 независимыми
классами нужен отдельный forward+backward на каждый объясняемый класс.
"""

import logging

import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class GradCAMPlusPlus:
    """
    Хуки живут, пока объект не удалён/не вызван .remove() - создавайте на время
    одного запроса объяснения (не как singleton, в отличие от ModelService).
    """

    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module):
        self.model = model
        self.target_layer = target_layer
        self._activations: torch.Tensor | None = None
        self._gradients: torch.Tensor | None = None
        self._fwd_handle = target_layer.register_forward_hook(self._save_activation)
        self._bwd_handle = target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, module, inp, out):
        self._activations = out

    def _save_gradient(self, module, grad_input, grad_output):
        self._gradients = grad_output[0]

    def remove(self):
        self._fwd_handle.remove()
        self._bwd_handle.remove()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.remove()

    def compute(self, x: torch.Tensor, class_idx: int, target_len: int) -> np.ndarray:
        """
        x: [1, C, N] на device модели.
        Возвращает CAM длиной target_len, нормализованный в [0, 1].
        """
        self.model.zero_grad(set_to_none=True)
        logits = self.model(x)  # [1, n_classes]
        score = logits[0, class_idx]
        score.backward(retain_graph=False)

        A = self._activations[0]  # [K, T']
        grads = self._gradients[0]  # [K, T']

        # Практическая аппроксимация Grad-CAM++ (см. Chattopadhay et al. 2018) -
        # только через градиенты первого порядка (без явного double-backward),
        # именно так реализовано в подавляющем большинстве открытых библиотек.
        grads2 = grads**2
        grads3 = grads**3
        sum_A_grads3 = (A * grads3).sum(dim=1, keepdim=True)  # [K, 1]
        alpha_denom = 2 * grads2 + sum_A_grads3
        alpha_denom = torch.where(
            alpha_denom != 0, alpha_denom, torch.ones_like(alpha_denom)
        )
        alphas = grads2 / (alpha_denom + 1e-8)  # [K, T']

        weights = (F.relu(grads) * alphas).sum(dim=1)  # [K]
        cam = F.relu((weights.unsqueeze(1) * A).sum(dim=0))  # [T']

        cam = cam.detach().cpu().numpy()
        if cam.max() > 0:
            cam = cam / cam.max()

        cam_up = np.interp(
            np.linspace(0, len(cam) - 1, target_len),
            np.arange(len(cam)),
            cam,
        )
        return cam_up.astype(np.float32)


def integrated_gradients(
    model: torch.nn.Module,
    x: torch.Tensor,
    class_idx: int,
    steps: int = 50,
    batch_size: int = 10,
    baseline: torch.Tensor | None = None,
) -> np.ndarray:
    """
    x: [1, C, N] на device модели.
    baseline: [1, C, N] или None -> нулевой вектор (после нашего препроцессинга
      это физически осмысленный "no signal": constant-0 сигнал после z-score
      с std=0+eps даёт ровно 0 в том же пространстве, где обучалась модель).
    Возвращает attribution [C, N] (numpy, тот же shape что вход без batch-оси).
    """
    device = x.device
    x0 = x[0].detach()  # [C, N]
    baseline0 = baseline[0].detach() if baseline is not None else torch.zeros_like(x0)

    alphas = torch.linspace(0, 1, steps, device=device)
    total_grads = torch.zeros_like(x0)

    model.zero_grad(set_to_none=True)
    for i in range(0, steps, batch_size):
        chunk_alphas = alphas[i : i + batch_size]  # [b]
        chunk = baseline0.unsqueeze(0) + chunk_alphas.view(-1, 1, 1) * (
            x0 - baseline0
        ).unsqueeze(
            0
        )  # [b, C, N]
        chunk = chunk.clone().requires_grad_(True)
        logits = model(chunk)  # [b, n_classes]
        scores = logits[:, class_idx].sum()
        grads = torch.autograd.grad(scores, chunk)[0]  # [b, C, N]
        total_grads += grads.sum(dim=0)

    avg_grads = total_grads / steps
    ig = (x0 - baseline0) * avg_grads
    return ig.detach().cpu().numpy()  # [C, N]


def combine_maps(grad_cam: np.ndarray, ig: np.ndarray) -> np.ndarray:
    """
    grad_cam: [N] в [0, 1] (общая по всем отведениям).
    ig: [C, N] сырой Integrated Gradients (может быть отрицательным).
    Возвращает combined [C, N] в [0, 1] - произведение нормализованных карт:
    высокое значение только там, где ОБА метода согласны, что место важно.
    """
    ig_abs = np.abs(ig)
    ig_norm = ig_abs / (ig_abs.max() + 1e-8)
    combined = grad_cam[None, :] * ig_norm  # broadcast по отведениям
    if combined.max() > 0:
        combined = combined / combined.max()
    return combined.astype(np.float32)


def explain_class(
    model: torch.nn.Module,
    target_layer: torch.nn.Module,
    x: torch.Tensor,
    class_idx: int,
    target_len: int,
    ig_steps: int = 50,
) -> dict:
    """Единая точка входа: считает Grad-CAM++, IG и комбинацию для одного класса."""
    with GradCAMPlusPlus(model, target_layer) as cam_engine:
        grad_cam = cam_engine.compute(x, class_idx, target_len)

    ig = integrated_gradients(model, x, class_idx, steps=ig_steps)
    combined = combine_maps(grad_cam, ig)

    return {"grad_cam": grad_cam, "integrated_gradients": ig, "combined": combined}
