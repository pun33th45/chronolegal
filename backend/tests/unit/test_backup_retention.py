"""Tests scripts/backup/prune_backups.sh directly via subprocess — pure file
operations on a tmp_path, no Docker/Postgres needed. Retention correctness
(especially "never delete the newest backup") is exactly the kind of logic
that's easy to get subtly wrong under edge cases, so it's tested in
isolation from the Docker-dependent backup/restore round trip
(tests/integration/test_backup_restore.py).
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "backup" / "prune_backups.sh"
)


def _touch(path: Path, days_old: int) -> None:
    path.write_text("fake dump content")
    ts = time.time() - days_old * 86_400
    os.utime(path, (ts, ts))


def _run(backup_dir: Path, retention_days: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "bash",
            str(_SCRIPT),
            str(backup_dir),
            str(retention_days),
            "chronolegal_*.dump",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture(autouse=True)
def _skip_if_no_bash():
    try:
        subprocess.run(
            ["bash", "--version"], capture_output=True, timeout=5, check=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("bash not available in this environment")


def test_prune_with_zero_backups_does_nothing(tmp_path):
    result = _run(tmp_path, 14)
    assert result.returncode == 0
    assert "no backups found" in result.stdout


def test_prune_keeps_the_only_backup_even_if_old(tmp_path):
    only = tmp_path / "chronolegal_20200101T000000Z.dump"
    _touch(only, days_old=365)

    result = _run(tmp_path, 14)

    assert result.returncode == 0
    assert (
        only.exists()
    ), "the single backup must survive even though it's far outside the retention window"


def test_prune_removes_old_but_keeps_recent(tmp_path):
    old = tmp_path / "chronolegal_old.dump"
    recent = tmp_path / "chronolegal_recent.dump"
    _touch(old, days_old=30)
    _touch(recent, days_old=1)

    result = _run(tmp_path, 14)

    assert result.returncode == 0
    assert not old.exists(), "backups older than the retention window should be removed"
    assert recent.exists()


def test_prune_never_deletes_the_newest_even_if_all_are_expired(tmp_path):
    oldest = tmp_path / "chronolegal_oldest.dump"
    newest = tmp_path / "chronolegal_newest.dump"
    _touch(oldest, days_old=90)
    _touch(newest, days_old=60)

    result = _run(tmp_path, 14)

    assert result.returncode == 0
    assert not oldest.exists()
    assert (
        newest.exists()
    ), "the newest backup must never be deleted, even if it's outside the retention window too"


def test_prune_with_retention_zero_disables_pruning(tmp_path):
    ancient = tmp_path / "chronolegal_ancient.dump"
    _touch(ancient, days_old=1000)

    result = _run(tmp_path, 0)

    assert result.returncode == 0
    assert ancient.exists(), "retention_days=0 must disable pruning entirely"


def test_prune_ignores_files_that_dont_match_the_glob(tmp_path):
    unrelated = tmp_path / "some_other_file.txt"
    _touch(unrelated, days_old=365)
    backup = tmp_path / "chronolegal_recent.dump"
    _touch(backup, days_old=1)

    result = _run(tmp_path, 14)

    assert result.returncode == 0
    assert (
        unrelated.exists()
    ), "prune must only ever touch files matching the backup glob pattern"


def test_prune_rejects_a_nonexistent_directory():
    result = _run(Path("/nonexistent/does/not/exist"), 14)
    assert result.returncode != 0


def test_prune_rejects_a_non_numeric_retention_value(tmp_path):
    result = _run(tmp_path, "not-a-number")  # type: ignore[arg-type]
    assert result.returncode != 0
