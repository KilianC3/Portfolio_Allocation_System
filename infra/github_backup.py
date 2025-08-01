from __future__ import annotations

"""Backup utility to persist scraped data to a GitHub repository."""

import os
import datetime as dt
from pathlib import Path
from typing import List, Dict

import pandas as pd

try:
    from git import Repo
except Exception:  # pragma: no cover - optional dependency
    Repo = None

from service.logger import get_logger

BACKUP_REPO = os.environ.get("BACKUP_REPO", "https://github.com/KilianC3/Backup.git")
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "backup"))

log = get_logger(__name__)


def _init_repo() -> "Repo | None":
    if Repo is None:
        return None
    if (BACKUP_DIR / ".git").exists():
        return Repo(BACKUP_DIR)
    try:
        log.info("cloning backup repo %s", BACKUP_REPO)
        return Repo.clone_from(BACKUP_REPO, BACKUP_DIR)
    except Exception as exc:  # pragma: no cover - network optional
        log.warning("backup clone failed: %s", exc)
        return None


def backup_records(table: str, records: List[Dict]) -> None:
    """Append ``records`` to ``table`` CSV and push to GitHub if possible."""
    if not records:
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    csv_file = BACKUP_DIR / f"{table}.csv"
    df_new = pd.DataFrame(records)
    df_new.insert(0, "_backup_ts", dt.datetime.now(dt.timezone.utc))
    if csv_file.exists():
        try:
            df_old = pd.read_csv(csv_file)
            df_new = pd.concat([df_old, df_new], ignore_index=True)
        except Exception as exc:  # pragma: no cover - corrupted file
            log.warning("backup read failed: %s", exc)
    df_new.to_csv(csv_file, index=False)

    repo = _init_repo()
    if repo is None:
        return
    try:
        repo.git.add(csv_file)
        if repo.is_dirty():
            repo.index.commit(f"update {table} {dt.date.today()}")
            repo.git.push("origin", "HEAD:main")
    except Exception as exc:  # pragma: no cover - network optional
        log.warning("backup push failed: %s", exc)
