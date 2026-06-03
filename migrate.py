"""
Apply schema.sql to the configured database.

Usage:
    python migrate.py
"""

import asyncio
from pathlib import Path

import asyncpg

from app.config import settings

SCHEMA = Path(__file__).parent / "schema.sql"


async def migrate() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(SCHEMA.read_text())
        print(f"✓ Schema applied to {settings.database_url.split('@')[-1]}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
