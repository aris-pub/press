"""Reset the database schema for preview deployments.

Drops and recreates the public schema so alembic can run from scratch.
"""

import asyncio
import os
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _fix_asyncpg_url(url: str) -> str:
    """Strip sslmode from URL since asyncpg uses 'ssl' parameter instead."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params.pop("sslmode", None)
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


async def reset():
    url = os.environ["DATABASE_URL"]
    url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    url = _fix_asyncpg_url(url)
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()
    print("Database schema reset complete.")


if __name__ == "__main__":
    asyncio.run(reset())
