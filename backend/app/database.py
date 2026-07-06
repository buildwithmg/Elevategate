from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Force every connection's session timezone to UTC. Without this, timestamptz columns come back
# from psycopg with whatever offset the Postgres server/OS is configured with (e.g. +04:00) - the
# stored instant is always correct either way, but every "*_at"/"*Utc" field in API responses
# should actually say +00:00, not just be UTC-equivalent under the hood.
engine = create_async_engine(
    settings.database_url, pool_pre_ping=True, connect_args={"options": "-c timezone=utc"}
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
