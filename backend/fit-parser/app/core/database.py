from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.infrastructure.database.models import Base

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Bootstrap para bases nuevas de desarrollo; no reemplaza migraciones."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "SELECT create_hypertable('telemetry_records', 'timestamp', "
            "if_not_exists => TRUE, migrate_data => TRUE)"
        ))
