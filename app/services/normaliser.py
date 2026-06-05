import re
import uuid
from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Category, Item

MATCH_THRESHOLD = 90


def normalize_name(raw_name: str) -> str:
    """Return a lowercased, plural-stemmed, whitespace-collapsed name for fuzzy comparison."""
    name = raw_name.lower().strip()
    # Strip store product codes like "043-2743-8" at the start
    name = re.sub(r"^\d{3}-\d{4}-\d\s*", "", name)
    tokens = name.split()
    # Simple plural normalization: "bananas" → "banana", "cookies" → "cookie"
    # Guards: token must be >3 chars, and not end in 'ss' (e.g. "grass" is fine, "bass" → "ba" is wrong)
    stemmed = []
    for t in tokens:
        if len(t) > 3 and t.endswith('s') and not t.endswith('ss'):
            stemmed.append(t[:-1])
        else:
            stemmed.append(t)
    return " ".join(stemmed)


def _is_token_prefix(shorter: list[str], longer: list[str]) -> bool:
    """True when shorter's tokens appear at the start of longer's tokens."""
    return len(shorter) <= len(longer) and longer[:len(shorter)] == shorter


async def get_category(session: AsyncSession, slug: str) -> Optional[Category]:
    """Look up a category by slug, falling back to 'other' for unknown slugs from OCR."""
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
    """Fuzzy-match raw_name against existing items; create a new Item only if no match meets the threshold.

    Matching strategy:
    - If one item's tokens are a prefix of the other's (e.g. "banana" ⊂ "banana organic",
      "banana" ⊂ "banana plt rp cs"), use token_set_ratio — scores 100 for these variants.
    - Otherwise use token_sort_ratio — prevents false merges like "butter" ↔ "peanut butter"
      where "butter" is NOT a prefix of "peanut butter".
    - On tie, prefer the shorter (more canonical) existing name.
    """
    normalized = normalize_name(raw_name)

    result = await session.execute(select(Item))
    existing: list[Item] = list(result.scalars().all())

    if existing:
        tokens_n = normalized.split()
        best_item: Optional[Item] = None
        best_score = 0

        for item in existing:
            tokens_e = item.normalized_name.split()
            short, long = (tokens_n, tokens_e) if len(tokens_n) <= len(tokens_e) else (tokens_e, tokens_n)

            if _is_token_prefix(short, long):
                score = fuzz.token_set_ratio(normalized, item.normalized_name)
            else:
                score = fuzz.token_sort_ratio(normalized, item.normalized_name)

            if score >= MATCH_THRESHOLD and (
                score > best_score
                or (score == best_score and best_item is not None
                    and len(item.normalized_name) < len(best_item.normalized_name))
            ):
                best_score = score
                best_item = item

        if best_item:
            return best_item

    category = await get_category(session, category_slug)
    new_item = Item(
        normalized_name=normalized,
        category_id=category.id if category else None,
    )
    session.add(new_item)
    await session.flush()
    return new_item
