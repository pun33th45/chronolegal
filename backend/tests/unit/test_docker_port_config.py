"""Verifies the production Docker CMD respects a PaaS-injected $PORT (e.g.
Render) while still defaulting to 8000 for local/Docker Compose use, where
PORT is never set. Building the actual image isn't practical in this
environment, but the CMD's shell-parameter-expansion behavior is directly
testable via sh, which is what actually determines the bound port.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

_DOCKERFILE = Path(__file__).resolve().parents[3] / "backend" / "Dockerfile"


@pytest.fixture(autouse=True)
def _skip_if_no_sh():
    try:
        subprocess.run(["sh", "-c", "true"], capture_output=True, timeout=5, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("sh not available in this environment")


def _production_cmd_line() -> str:
    text = _DOCKERFILE.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^FROM base AS production.*?^CMD\s+(.+)$", text)
    assert match, "Could not find production stage CMD in backend/Dockerfile"
    return match.group(1).strip()


def test_production_cmd_is_shell_form_not_exec_form():
    cmd = _production_cmd_line()
    assert not cmd.startswith("["), (
        "Production CMD must be shell form (not JSON-array exec form) so "
        "${PORT:-8000} is expanded by the shell at container startup"
    )


def test_production_cmd_defaults_to_8000_when_port_unset():
    cmd = _production_cmd_line()
    env = {k: v for k, v in os.environ.items() if k != "PORT"}
    result = subprocess.run(
        ["sh", "-c", f"echo {cmd}"], capture_output=True, text=True, timeout=5, env=env
    )
    assert "--port 8000" in result.stdout


def test_production_cmd_uses_injected_port_when_set():
    cmd = _production_cmd_line()
    env = {**os.environ, "PORT": "5050"}
    result = subprocess.run(
        ["sh", "-c", f"echo {cmd}"], capture_output=True, text=True, timeout=5, env=env
    )
    assert "--port 5050" in result.stdout
    assert "--port 8000" not in result.stdout
