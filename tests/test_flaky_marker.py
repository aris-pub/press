"""Tests marked flaky still run locally but never block a merge in CI.

A flaky test gets a bead to find its cause. The marker is not a place to leave it.
"""

import ast
from pathlib import Path
import tomllib

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_flaky_marker_is_registered():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    markers = config["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("flaky:") for m in markers)


def test_every_e2e_ci_job_skips_flaky_tests():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    jobs = workflow["jobs"]["e2e"]["strategy"]["matrix"]["include"]
    assert jobs
    for job in jobs:
        assert job["marker"].endswith(" and not flaky"), job["name"]


def test_mobile_menu_navigation_is_marked_flaky():
    """It failed 2 of 5 CI runs in WebKit with the page left on / (2026-11-06)."""
    source = (ROOT / "tests/e2e/test_auth_flows_mobile.py").read_text()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "test_mobile_menu_navigation":
            names = [ast.unparse(d) for d in node.decorator_list]
            assert "pytest.mark.flaky" in names
            return
    raise AssertionError("test_mobile_menu_navigation not found")
