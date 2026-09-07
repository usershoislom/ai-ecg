"""
codegen.py

Врач при создании кастомного класса вводит ТОЛЬКО название (на своём языке) -
машинный уникальный `code` (нужен только внутри системы: FK, логи, будущая
интеграция) генерируется здесь автоматически.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    # узбекская кириллица, специфичные буквы сверх пересечения с русской
    "ў": "o",
    "қ": "q",
    "ғ": "g",
    "ҳ": "h",
}

_PREFERRED_LANG_ORDER = ["ru", "uz", "en"]


def _transliterate(text: str) -> str:
    return "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in text.lower())


def _slugify(text: str) -> str:
    translit = _transliterate(text)
    slug = re.sub(r"[^a-z0-9]+", "_", translit).strip("_")
    return slug.upper()[:40] or "CLASS"


def _pick_base_name(names: dict[str, str]) -> str:
    for lang in _PREFERRED_LANG_ORDER:
        if names.get(lang):
            return names[lang]
    return next(iter(names.values()))  # любой другой язык, если ru/uz/en не заданы


async def generate_unique_code(
    db: AsyncSession, model_cls, names: dict[str, str]
) -> str:
    """model_cls - класс SQLAlchemy-модели с колонкой `code` (AnnotationClass)."""
    base = _slugify(_pick_base_name(names))
    candidate = base
    suffix = 2
    while True:
        existing = (
            await db.execute(select(model_cls).where(model_cls.code == candidate))
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base}_{suffix}"
        suffix += 1
