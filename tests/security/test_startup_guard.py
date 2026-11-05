"""The app must refuse to start with test-only switches on a deployed server."""

import os
import subprocess
import sys

import pytest

from app.startup_guard import check_test_switches


@pytest.mark.parametrize("switch", ["TESTING", "E2E_TESTING"])
@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", " 1 "])
@pytest.mark.parametrize(
    "deployed", [{"FLY_APP_NAME": "scroll-press"}, {"ENVIRONMENT": "production"}]
)
def test_refuses_test_switch_when_deployed(switch, value, deployed):
    with pytest.raises(RuntimeError, match=switch):
        check_test_switches({switch: value, **deployed})


def test_names_every_switch_that_is_on():
    with pytest.raises(RuntimeError, match="TESTING, E2E_TESTING"):
        check_test_switches({"TESTING": "1", "E2E_TESTING": "1", "FLY_APP_NAME": "x"})


@pytest.mark.parametrize(
    "env",
    [
        {"TESTING": "1", "E2E_TESTING": "1"},
        {"TESTING": "1", "ENVIRONMENT": "development"},
        {"E2E_TESTING": "1", "ENVIRONMENT": "preview"},
        {"FLY_APP_NAME": "scroll-press", "ENVIRONMENT": "production"},
        {"FLY_APP_NAME": "scroll-press", "TESTING": "0", "E2E_TESTING": "false"},
        {"FLY_APP_NAME": "scroll-press", "TESTING": ""},
        {},
    ],
)
def test_allows_everything_else(env):
    check_test_switches(env)


def test_importing_the_app_fails_on_fly_with_a_test_switch(tmp_path):
    """The guard runs at import, before the app is built, so uvicorn cannot start."""
    env = {**os.environ, "FLY_APP_NAME": "scroll-press", "E2E_TESTING": "1", "TESTING": ""}
    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "Refusing to start" in result.stderr
