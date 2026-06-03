from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    # Required for Supabase: PgBouncer in transaction mode doesn't support
    # named prepared statements — disable asyncpg's cache to avoid
    # "prepared statement does not exist" errors at deploy time.
    connect_args={"prepared_statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
