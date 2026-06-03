import re
import uuid
from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Category, Item

# Items whose normalized names score at or above this threshold are considered
# the same product. Erring high avoids false merges (hard to unwind) since
# raw_name is always preserved on every receipt_item for search fallback.
MATCH_THRESHOLD = 90


def normalize_name(raw_name: str) -> str:
    """Return a lowercased, whitespace-collapsed name for fuzzy comparison."""
    name = raw_name.lower().strip()
    # Strip store product codes like "043-2743-8" at the start
    name = re.sub(r"^\d{3}-\d{4}-\d\s*", "", name)
    # Collapse multiple spaces
    name = " ".join(name.split())
    return name


async def get_category(session: AsyncSession, slug: str) -> Optional[Category]:
    result = await session.execute(select(Category).where(Category.slug == slug))
    cat = result.scalar_one_or_none()
    if cat:
        return cat
    # Fall back to 'other' if the slug from OCR doesn't match any seed category
    result = await session.execute(select(Category).where(Category.slug == "other"))
    return result.scalar_one_or_none()


async def find_or_create_item(
    session: AsyncSession,
    raw_name: str,
    category_slug: str,
) -> Item:
    normalized = normalize_name(raw_name)

    # Load all existing items into memory — fast enough for a personal app
    # (hundreds to low thousands of distinct items at most).
    result = await session.execute(select(Item))
    existing: list[Item] = list(result.scalars().all())

    if existing:
        choices = {str(item.id): item.normalized_name for item in existing}
        match = process.extractOne(
            normalized,
            choices,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=MATCH_THRESHOLD,
        )
        if match:
            matched_id = uuid.UUID(match[2])
            return next(item for item in existing if item.id == matched_id)

    category = await get_category(session, category_slug)
    new_item = Item(
        normalized_name=normalized,
        category_id=category.id if category else None,
    )
    session.add(new_item)
    await session.flush()
    return new_item
