"""SQL statement logging must stay off unless SQL_ECHO=1."""

import os

import pytest

from app.database import engine


@pytest.mark.skipif(os.getenv("SQL_ECHO") == "1", reason="SQL_ECHO=1 turns logging on")
def test_sql_echo_off_by_default():
    assert engine.echo is False
