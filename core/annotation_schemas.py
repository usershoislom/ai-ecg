import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ClassOut(BaseModel):
    id: uuid.UUID
    type: Literal["superclass", "subclass"]
    code: str
    name: str  # уже переведено под запрошенный lang
    parent_class_id: uuid.UUID | None
    is_custom: bool

    class Config:
        from_attributes = True


class SuperclassWithSubclassesOut(BaseModel):
    """
    Суперкласс + вложенные подклассы - иерархический ответ GET /annotation/classes.
    id=None используется ТОЛЬКО для синтетического узла "Без категории" (подклассы,
    чей родительский суперкласс деактивирован/удалён, но сам подкласс всё ещё
    активен и используется в существующих аннотациях) - такой узел не является
    реальным суперклассом и не годится для выбора врачом как superclass_id.
    """

    id: uuid.UUID | None
    code: str | None
    name: str
    is_custom: bool = False
    subclasses: list[ClassOut]


class ClassCreate(BaseModel):
    type: Literal["superclass", "subclass"]
    names: dict[str, str] = Field(
        ...,
        description='напр. {"ru": "...", "uz": "..."} - минимум один язык. Машинный код (code) генерируется автоматически, врачу вводить его не нужно.',
    )
    parent_class_id: uuid.UUID | None = Field(
        None, description="обязателен для type=subclass"
    )

    @field_validator("names")
    @classmethod
    def _names_not_empty(cls, v):
        if not v:
            raise ValueError("names не может быть пустым - нужен хотя бы один язык")
        return v


class AnnotationCreate(BaseModel):
    study_instance_uid: str
    series_instance_uid: str | None = None
    sop_instance_uid: str | None = None
    doctor_id: str | None = None
    superclass_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="минимум один суперкласс (в т.ч. OTHER)"
    )
    subclass_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="минимум один подкласс"
    )
    other_text: str | None = None


class AnnotationOut(BaseModel):
    id: uuid.UUID
    study_instance_uid: str
    series_instance_uid: str | None
    sop_instance_uid: str | None
    doctor_id: str | None
    other_text: str | None
    superclasses: list[ClassOut]
    subclasses: list[ClassOut]
    created_at: str
    updated_at: str
