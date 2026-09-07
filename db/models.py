"""
models.py

Схема:
- annotation_classes: суперклассы и подклассы, мультиязычные названия в JSONB,
  soft delete через is_active (жёсткое удаление сломало бы историю аннотаций,
  которые уже ссылаются на класс).
- Иерархия УПРОЩЕНА по явному запросу "максимально быстро, но архитектурно
  правильно направление": подкласс привязан к ОДНОМУ суперклассу через
  parent_class_id (не many-to-many). Расширить до many-to-many можно потом
  отдельной таблицей-мостиком без ломающих изменений схемы annotation_classes.
- annotations: одно исследование (study) может иметь НЕСКОЛЬКО аннотаций
  (разные врачи) - никакой блокировки/upsert-логики не нужно, просто INSERT.
- doctor_id - свободная строка без проверки, т.к. auth ещё не подключена.
- Истории изменений (annotation_history) сознательно НЕТ в этой версии -
  отложено, PUT пока перезаписывает текущее состояние.
"""

import enum
import uuid

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    Table,
    Column,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class ClassType(str, enum.Enum):
    superclass = "superclass"
    subclass = "subclass"


annotation_class_links = Table(
    "annotation_class_links",
    Base.metadata,
    Column(
        "annotation_id",
        UUID(as_uuid=True),
        ForeignKey("annotations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "class_id",
        UUID(as_uuid=True),
        ForeignKey("annotation_classes.id"),
        primary_key=True,
    ),
)


class AnnotationClass(Base):
    __tablename__ = "annotation_classes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[ClassType] = mapped_column(
        Enum(ClassType, name="class_type"), nullable=False
    )
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    names: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # {"ru": "...", "uz": "..."}
    parent_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("annotation_classes.id"), nullable=True
    )
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def name_for(self, lang: str, fallback_lang: str = "ru") -> str:
        """Переведённое название с фолбэком на fallback_lang, затем на code, если и его нет."""
        return self.names.get(lang) or self.names.get(fallback_lang) or self.code


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    study_instance_uid: Mapped[str] = mapped_column(String, nullable=False, index=True)
    series_instance_uid: Mapped[str | None] = mapped_column(String, nullable=True)
    sop_instance_uid: Mapped[str | None] = mapped_column(String, nullable=True)
    doctor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    other_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    classes: Mapped[list[AnnotationClass]] = relationship(
        AnnotationClass, secondary=annotation_class_links, lazy="selectin"
    )
