"""
One-time script: merge duplicate Item rows using the same prefix-aware fuzzy logic
as the normaliser, then re-point their ReceiptItem rows to the canonical item.

Uses raw asyncpg (not SQLAlchemy) to avoid prepared-statement issues with PgBouncer.

Run from backend/:
    python merge_items.py
"""

import asyncio
import uuid
from collections import defaultdict

import asyncpg
from rapidfuzz import fuzz

from app.config import settings
from app.services.normaliser import normalize_name, MATCH_THRESHOLD

THRESHOLD = MATCH_THRESHOLD


def _is_token_prefix(shorter: list[str], longer: list[str]) -> bool:
    return len(shorter) <= len(longer) and longer[:len(shorter)] == shorter


def _score(a: str, b: str) -> int:
    ta, tb = a.split(), b.split()
    short, long = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if _is_token_prefix(short, long):
        return fuzz.token_set_ratio(a, b)
    return fuzz.token_sort_ratio(a, b)


def build_merge_groups(rows: list[asyncpg.Record]) -> list[list[asyncpg.Record]]:
    """Union-find grouping by re-normalized name similarity."""
    norms = {row["id"]: normalize_name(row["normalized_name"]) for row in rows}

    ids = [row["id"] for row in rows]
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if _score(norms[a], norms[b]) >= THRESHOLD:
                union(a, b)

    groups: dict = defaultdict(list)
    for row in rows:
        groups[find(row["id"])].append(row)

    return [g for g in groups.values() if len(g) > 1]


def pick_canonical(group: list[asyncpg.Record]) -> asyncpg.Record:
    """Prefer the item with the shortest normalized_name (most generic)."""
    return min(group, key=lambda r: (len(r["normalized_name"]), str(r["id"])))


async def run() -> None:
    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        rows = await conn.fetch("SELECT id, normalized_name FROM items")
        print(f"Loaded {len(rows)} items.")

        groups = build_merge_groups(rows)
        if not groups:
            print("No duplicates found — nothing to merge.")
            return

        async with conn.transaction():
            for group in groups:
                canonical = pick_canonical(group)
                dupes = [r for r in group if r["id"] != canonical["id"]]
                dupe_ids = [r["id"] for r in dupes]

                print(
                    f"  Merging {[r['normalized_name'] for r in dupes]}"
                    f" → '{canonical['normalized_name']}'"
                )

                await conn.execute(
                    "UPDATE receipt_items SET item_id = $1 WHERE item_id = ANY($2::uuid[])",
                    canonical["id"],
                    dupe_ids,
                )
                await conn.execute(
                    "DELETE FROM items WHERE id = ANY($1::uuid[])",
                    dupe_ids,
                )

        print("Done.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
