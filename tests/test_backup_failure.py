import subprocess

import pytest

from database import backup


def test_backup_to_github_propagates_git_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(backup, "_dump_tables", lambda: [tmp_path / "t.json"])

    def fail(cmd, check):  # pragma: no cover - simulated failure
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(backup.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        backup.backup_to_github()
