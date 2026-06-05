from collections.abc import AsyncGenerator

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


# NullPool lets PgBouncer own all connection pooling. SQLAlchemy gets a fresh
# connection from PgBouncer per request and releases it immediately after —
# no long-lived client-side pool means no stale prepared statements across
# PgBouncer's backend connection recycling.
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    poolclass=NullPool,
    connect_args={"prepared_statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a scoped async database session per request."""
    async with AsyncSessionLocal() as session:
        yield session
