from typing import Optional
from pydantic import BaseModel, Field


class ClassPrediction(BaseModel):
    label: str
    probability: float = Field(..., description="Sigmoid-вероятность класса, 0..1")
    threshold: float = Field(..., description="Порог принятия решения для этого класса")
    positive: bool = Field(..., description="probability >= threshold")


class PredictionResponse(BaseModel):
    predictions: list[ClassPrediction]
    positive_classes: list[str] = Field(..., description="Классы, где positive=True")
    source: dict = Field(
        default_factory=dict,
        description="Метаданные источника сигнала (fs, длительность, файл/UID и т.п.)",
    )


class PacsRequest(BaseModel):
    studyInstanceUID: str
    seriesInstanceUID: str
    sopInstanceUID: str


class WfdbRequest(BaseModel):
    record_name: str = Field(
        ...,
        description="Имя записи без расширения, относительно WFDB_ROOT, напр. 'records500/00000/00001_hr'",
    )


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class Measurement(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    value: float | str
    unit: Optional[str] = None
    is_voltage_criterion: bool = False


class MetadataResponse(BaseModel):
    patient: dict = Field(default_factory=dict)
    study: dict = Field(default_factory=dict)
    device: dict = Field(default_factory=dict)
    measurements: list[Measurement] = Field(default_factory=list)
    text_annotations: list[str] = Field(default_factory=list)


class RawClassPrediction(BaseModel):
    label: str
    probability: float = Field(
        ...,
        description="Сигмоид-вероятность класса, 0..1. Без порога - модель не откалибрована.",
    )


class RawPredictionResponse(BaseModel):
    """Ответ исходной (не дообученной) ECGFounder - 150 классов претрейна, без порогов."""

    predictions: list[RawClassPrediction]
    top_k: list[RawClassPrediction] = Field(
        ..., description="Топ-N классов по вероятности, для быстрого просмотра"
    )
    source: dict = Field(default_factory=dict)
