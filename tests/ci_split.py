"""Helpers that let CI run the test suite in parallel.

- `assign_files_to_shards` splits test files across CI jobs (`--shard i/n`).
- `per_worker_database_url` gives each pytest-xdist worker its own Postgres database.
"""

import asyncio


def assign_files_to_shards(test_counts: dict[str, int], shards: int) -> dict[str, int]:
    """Map each test file to a shard number (1 to `shards`).

    Files go, largest first, to the shard with the fewest tests so far. Whole files stay
    together because tests in one file often share setup. Every job computes the same
    split from the same collected tests, so no file is skipped or run twice.
    """
    loads = [0] * shards
    result = {}
    for path in sorted(test_counts, key=lambda p: (-test_counts[p], p)):
        shard = loads.index(min(loads))
        result[path] = shard + 1
        loads[shard] += test_counts[path]
    return result


def parse_shard(value: str) -> tuple[int, int]:
    """Parse "i/n" into (i, n) and check that 1 <= i <= n."""
    index, total = (int(part) for part in value.split("/"))
    if not 1 <= index <= total:
        raise ValueError(f"--shard must be i/n with 1 <= i <= n, got {value!r}")
    return index, total


def per_worker_database_url(url: str, worker: str) -> str:
    """Return `url` pointed at a database for this xdist worker, creating it if needed.

    The test_db fixture creates and drops every table around each test. Workers sharing
    one database deadlocked and hit unique-constraint errors, which is why xdist was
    removed from CI three times (87779fb, cf9d700, 2120b0d). One database per worker
    removes the sharing.
    """
    from sqlalchemy.engine import make_url

    base = make_url(url)
    name = f"{base.database}_{worker}"
    asyncio.run(_create_database(base, name))
    return base.set(database=name).render_as_string(hide_password=False)


async def _create_database(base, name: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(
        host=base.host,
        port=base.port,
        user=base.username,
        password=base.password,
        database=base.database,
    )
    try:
        await conn.execute(f'CREATE DATABASE "{name}"')
    except asyncpg.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()
