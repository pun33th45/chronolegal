"""Tests scripts/backup/sync_offhost.sh's safe-by-default behavior directly
via subprocess. This is deliberately NOT a test of a working off-host
transfer — no real remote host is available in CI or this environment (see
the Phase 5 report) — it only proves the script does nothing destructive
and fails clearly when misconfigured, which is exactly what's verifiable
without real remote infrastructure.
"""

import os
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "backup" / "sync_offhost.sh"


@pytest.fixture(autouse=True)
def _skip_if_no_bash():
    try:
        subprocess.run(
            ["bash", "--version"], capture_output=True, timeout=5, check=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("bash not available in this environment")


def _run(env_overrides: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for key in (
        "OFFHOST_BACKUP_HOST",
        "OFFHOST_BACKUP_PATH",
        "OFFHOST_SSH_KEY",
        "BACKUP_DIR",
    ):
        env.pop(key, None)
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(_SCRIPT)], capture_output=True, text=True, timeout=30, env=env
    )


def test_sync_is_a_noop_when_offhost_host_is_unset():
    result = _run({})
    assert result.returncode == 0
    assert "disabled" in result.stdout


def test_sync_fails_clearly_when_path_is_missing(tmp_path):
    (tmp_path / "chronolegal_x.dump").write_text("fake")
    result = _run(
        {
            "OFFHOST_BACKUP_HOST": "backup-user@example.invalid",
            "BACKUP_DIR": str(tmp_path),
        }
    )
    assert result.returncode != 0
    assert "OFFHOST_BACKUP_PATH" in result.stderr


def test_sync_fails_clearly_when_no_local_backups_exist(tmp_path):
    result = _run(
        {
            "OFFHOST_BACKUP_HOST": "backup-user@example.invalid",
            "OFFHOST_BACKUP_PATH": "/backups",
            "BACKUP_DIR": str(tmp_path),
        }
    )
    assert result.returncode != 0
    assert "no local backups found" in result.stderr
