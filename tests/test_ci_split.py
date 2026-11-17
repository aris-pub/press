"""Tests for tests/ci_split.py, which CI uses to run tests in parallel."""

import pytest

from tests.ci_split import assign_files_to_shards, parse_shard


def test_every_file_gets_exactly_one_shard():
    counts = {f"tests/e2e/test_{i}.py": i + 1 for i in range(20)}
    result = assign_files_to_shards(counts, 3)
    assert set(result) == set(counts)
    assert set(result.values()) == {1, 2, 3}


def test_shards_are_balanced_by_test_count():
    counts = {"a.py": 9, "b.py": 5, "c.py": 4, "d.py": 3, "e.py": 3, "f.py": 2}
    result = assign_files_to_shards(counts, 3)
    loads = [sum(c for f, c in counts.items() if result[f] == s) for s in (1, 2, 3)]
    assert max(loads) - min(loads) <= 2


def test_split_does_not_depend_on_input_order():
    """Each CI job computes the split on its own, so all jobs must get the same answer."""
    counts = {"a.py": 3, "b.py": 3, "c.py": 1, "d.py": 2}
    reordered = dict(reversed(list(counts.items())))
    assert assign_files_to_shards(counts, 2) == assign_files_to_shards(reordered, 2)


def test_parse_shard():
    assert parse_shard("2/3") == (2, 3)
    for bad in ("0/3", "4/3"):
        with pytest.raises(ValueError):
            parse_shard(bad)
