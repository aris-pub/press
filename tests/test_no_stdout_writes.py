"""Server code logs through `logging`, never by writing to stdout.

A bare print fails when stdout has no reader. In CI the test server's stdout
closed when its step ended, and the upload route's memory-profiling prints
turned every upload into a 500 (PR #78, run 42174365709).
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_FILES = [ROOT / "main.py", *sorted((ROOT / "app").rglob("*.py"))]


def _stdout_writes(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        if name == "print" or name.startswith("sys.stdout."):
            found.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}")
    return found


def test_server_code_never_writes_to_stdout():
    found = [hit for path in SERVER_FILES for hit in _stdout_writes(path)]
    assert found == []


def test_memory_profiling_middleware_is_gone():
    assert not (ROOT / "app/memory_profiling_middleware.py").exists()
    assert "MemoryProfilingMiddleware" not in (ROOT / "main.py").read_text()
