"""
annotation_router.py

Эндпоинты аннотирования ЭКГ врачом. Быстрый MVP по явному запросу пользователя:
без auth (doctor_id - свободная строка), без истории изменений (PUT
перезаписывает), иерархия классов упрощена (подкласс -> один суперкласс).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import get_db
from db.models import Annotation, AnnotationClass, ClassType
from core.annotation_schemas import (
    AnnotationCreate,
    AnnotationOut,
    ClassCreate,
    ClassOut,
)
from core.codegen import generate_unique_code

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/annotation", tags=["annotation"])


def _class_to_out(cls: AnnotationClass, lang: str) -> ClassOut:
    return ClassOut(
        id=cls.id,
        type=cls.type.value,
        code=cls.code,
        name=cls.name_for(lang),
        parent_class_id=cls.parent_class_id,
        is_custom=cls.is_custom,
    )


def _annotation_to_out(ann: Annotation, lang: str) -> AnnotationOut:
    superclasses = [
        _class_to_out(c, lang) for c in ann.classes if c.type == ClassType.superclass
    ]
    subclasses = [
        _class_to_out(c, lang) for c in ann.classes if c.type == ClassType.subclass
    ]
    return AnnotationOut(
        id=ann.id,
        study_instance_uid=ann.study_instance_uid,
        series_instance_uid=ann.series_instance_uid,
        sop_instance_uid=ann.sop_instance_uid,
        doctor_id=ann.doctor_id,
        other_text=ann.other_text,
        superclasses=superclasses,
        subclasses=subclasses,
        created_at=ann.created_at.isoformat(),
        updated_at=ann.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Классы (суперклассы/подклассы)
# ---------------------------------------------------------------------------


@router.get("/classes/", response_model=list[ClassOut])
async def list_classes(
    lang: str = Query("ru"),
    type: str | None = Query(
        None, description="superclass | subclass, без параметра - все"
    ),
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AnnotationClass)
    if not include_inactive:
        stmt = stmt.where(AnnotationClass.is_active == True)  # noqa: E712
    if type:
        try:
            stmt = stmt.where(AnnotationClass.type == ClassType(type))
        except ValueError:
            raise HTTPException(
                status_code=400, detail="type должен быть 'superclass' или 'subclass'"
            )

    rows = (await db.execute(stmt)).scalars().all()
    return [_class_to_out(c, lang) for c in rows]


@router.get("/classes/{class_id}/", response_model=ClassOut)
async def get_class(
    class_id: uuid.UUID, lang: str = Query("ru"), db: AsyncSession = Depends(get_db)
):
    cls = await db.get(AnnotationClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Класс не найден")
    return _class_to_out(cls, lang)


@router.post("/classes/", response_model=ClassOut, status_code=201)
async def create_class(
    payload: ClassCreate, lang: str = Query("ru"), db: AsyncSession = Depends(get_db)
):
    if payload.type == "subclass" and payload.parent_class_id is None:
        raise HTTPException(
            status_code=400, detail="Для подкласса обязателен parent_class_id"
        )

    if payload.parent_class_id is not None:
        parent = await db.get(AnnotationClass, payload.parent_class_id)
        if (
            parent is None
            or parent.type != ClassType.superclass
            or not parent.is_active
        ):
            raise HTTPException(
                status_code=400,
                detail="parent_class_id должен указывать на активный существующий суперкласс",
            )

    # Врач вводит только название - машинный code генерируется здесь автоматически
    # (транслитерация + гарантия уникальности), см. core/codegen.py.
    code = await generate_unique_code(db, AnnotationClass, payload.names)

    obj = AnnotationClass(
        type=ClassType(payload.type),
        code=code,
        names=payload.names,
        parent_class_id=payload.parent_class_id,
        is_custom=True,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return _class_to_out(obj, lang=lang)


@router.post("/classes/{class_id}/activate/", response_model=ClassOut)
async def activate_class(
    class_id: uuid.UUID,
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
):
    """
    Повторная активация ранее удаленного (деактивированного) класса.
    """
    cls = await db.get(AnnotationClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Класс не найден")

    if cls.is_active:
        # Если он уже активен, просто возвращаем его без ошибок
        return _class_to_out(cls, lang)

    cls.is_active = True
    await db.commit()
    await db.refresh(cls)

    return _class_to_out(cls, lang)


@router.delete("/classes/{class_id}/", status_code=204)
async def delete_class(class_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cls = await db.get(AnnotationClass, class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Класс не найден")
    # Soft delete - НЕ физическое удаление: класс может уже использоваться в
    # существующих аннотациях, hard delete сломал бы FK/историю.
    cls.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Аннотации
# ---------------------------------------------------------------------------


async def _load_and_validate_classes(
    db: AsyncSession, ids: list[uuid.UUID], expected_type: ClassType
) -> list[AnnotationClass]:
    if not ids:
        return []
    rows = (
        (await db.execute(select(AnnotationClass).where(AnnotationClass.id.in_(ids))))
        .scalars()
        .all()
    )
    found_ids = {c.id for c in rows}
    missing = set(ids) - found_ids
    if missing:
        raise HTTPException(status_code=400, detail=f"Классы не найдены: {missing}")
    wrong_type = [c.code for c in rows if c.type != expected_type]
    if wrong_type:
        raise HTTPException(
            status_code=400,
            detail=f"Ожидался тип {expected_type.value}, получены: {wrong_type}",
        )
    inactive = [c.code for c in rows if not c.is_active]
    if inactive:
        raise HTTPException(
            status_code=400, detail=f"Классы неактивны (удалены): {inactive}"
        )
    return rows


@router.get("/study/{study_instance_uid}/", response_model=list[AnnotationOut])
async def get_annotations_by_study(
    study_instance_uid: str,
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Annotation)
        .where(
            Annotation.study_instance_uid == study_instance_uid,
            Annotation.is_active == True,  # noqa: E712
        )
        .options(selectinload(Annotation.classes))
    )

    rows = (await db.execute(stmt)).scalars().all()
    return [_annotation_to_out(a, lang) for a in rows]


@router.get("/", response_model=list[AnnotationOut])
async def list_all_annotations(
    lang: str = Query("ru"),
    limit: int = Query(
        50, ge=1, le=100, description="Максимальное количество записей (пагинация)"
    ),
    offset: int = Query(0, ge=0, description="Сдвиг для пагинации"),
    doctor_id: str | None = Query(None, description="Опциональный фильтр по ID врача"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получение списка всех активных аннотаций с пагинацией и опциональной фильтрацией.
    """
    stmt = (
        select(Annotation)
        .where(
            Annotation.is_active == True,  # noqa: E712
        )
        .options(selectinload(Annotation.classes))
    )

    # Применяем фильтр по врачу, если он передан
    if doctor_id:
        stmt = stmt.where(Annotation.doctor_id == doctor_id)

    # Сортируем по дате создания (новые сверху) и применяем пагинацию
    stmt = stmt.order_by(Annotation.created_at.desc()).limit(limit).offset(offset)

    rows = (await db.execute(stmt)).scalars().all()
    return [_annotation_to_out(a, lang) for a in rows]


@router.get("/{annotation_id}/", response_model=AnnotationOut)
async def get_annotation(
    annotation_id: uuid.UUID,
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
):
    ann = await db.get(
        Annotation, annotation_id, options=[selectinload(Annotation.classes)]
    )
    if ann is None or not ann.is_active:
        raise HTTPException(status_code=404, detail="Аннотация не найдена")
    return _annotation_to_out(ann, lang)


@router.post("/", response_model=AnnotationOut, status_code=201)
async def create_annotation(
    payload: AnnotationCreate,
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
):
    superclasses = await _load_and_validate_classes(
        db, payload.superclass_ids, ClassType.superclass
    )
    subclasses = await _load_and_validate_classes(
        db, payload.subclass_ids, ClassType.subclass
    )

    ann = Annotation(
        study_instance_uid=payload.study_instance_uid,
        series_instance_uid=payload.series_instance_uid,
        sop_instance_uid=payload.sop_instance_uid,
        doctor_id=payload.doctor_id,
        other_text=payload.other_text,
        classes=list(superclasses) + list(subclasses),
    )
    db.add(ann)
    await db.commit()
    stmt = (
        select(Annotation)
        .where(Annotation.id == ann.id)
        .options(selectinload(Annotation.classes))
    )
    ann = (await db.execute(stmt)).scalar_one()
    # await db.refresh(ann, attribute_names=["classes"])
    return _annotation_to_out(ann, lang)


@router.put("/{annotation_id}/", response_model=AnnotationOut)
async def update_annotation(
    annotation_id: uuid.UUID,
    payload: AnnotationCreate,
    lang: str = Query("ru"),
    db: AsyncSession = Depends(get_db),
):
    ann = await db.get(Annotation, annotation_id)
    if ann is None or not ann.is_active:
        raise HTTPException(status_code=404, detail="Аннотация не найдена")

    superclasses = await _load_and_validate_classes(
        db, payload.superclass_ids, ClassType.superclass
    )
    subclasses = await _load_and_validate_classes(
        db, payload.subclass_ids, ClassType.subclass
    )

    ann.study_instance_uid = payload.study_instance_uid
    ann.series_instance_uid = payload.series_instance_uid
    ann.sop_instance_uid = payload.sop_instance_uid
    ann.doctor_id = payload.doctor_id
    ann.other_text = payload.other_text
    ann.classes = list(superclasses) + list(
        subclasses
    )  # PUT = полная замена, без истории (см. докстринг файла)

    await db.commit()
    # await db.refresh(ann, attribute_names=["classes"])
    stmt = (
        select(Annotation)
        .where(Annotation.id == ann.id)
        .options(selectinload(Annotation.classes))
    )
    ann = (await db.execute(stmt)).scalar_one()
    return _annotation_to_out(ann, lang)


@router.delete("/{annotation_id}/", status_code=204)
async def delete_annotation(
    annotation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    ann = await db.get(Annotation, annotation_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Аннотация не найдена")
    ann.is_active = False  # soft delete
    await db.commit()
