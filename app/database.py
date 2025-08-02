import os
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/press")

# Database configuration based on URL type
if "postgresql+asyncpg" in DATABASE_URL:
    # PostgreSQL with asyncpg - fix for Supabase/pgbouncer prepared statement issues
    connect_args = {
        "server_settings": {"jit": "off"},
        "command_timeout": 60,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex[:8]}__",
    }
    engine = create_async_engine(
        DATABASE_URL, echo=True, connect_args=connect_args, pool_pre_ping=True, poolclass=NullPool
    )
elif "postgresql" in DATABASE_URL:
    # PostgreSQL with other drivers (psycopg2, etc)
    engine = create_async_engine(DATABASE_URL, echo=True, pool_pre_ping=True, poolclass=NullPool)
else:
    # SQLite or other databases - no special connection args needed
    engine = create_async_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Models are imported via main.py and routes, ensuring they're registered with Base.metadata


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
