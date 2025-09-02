import json
import subprocess
import datetime as dt
from pathlib import Path
from typing import List

from . import db
from service.logger import get_logger

log = get_logger("backup")

BACKUP_DIR = Path(__file__).resolve().parent / "backups"


def _dump_tables() -> List[Path]:
    """Dump all database tables to ``BACKUP_DIR`` and return written paths."""
    if not db.conn:  # type: ignore[attr-defined]
        log.error("database connection not available")
        raise RuntimeError("database connection not available")
    BACKUP_DIR.mkdir(exist_ok=True)
    paths: List[Path] = []
    with db.conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute("SHOW TABLES")
        tables = [next(iter(r.values())) for r in cur.fetchall()]
    for table in tables:
        coll = db[table]
        rows = list(coll.find({}))
        p = BACKUP_DIR / f"{table}.json"
        with open(p, "w") as f:
            json.dump(rows, f, default=str)
        paths.append(p)
    return paths


def backup_to_github(message: str | None = None) -> None:
    """Export all tables and commit the snapshot to the git repository."""
    paths = _dump_tables()
    if not paths:
        log.error("no tables dumped")
        raise RuntimeError("no tables dumped")
    try:
        for p in paths:
            subprocess.run(["git", "add", str(p)], check=True)
        msg = message or f"DB backup {dt.datetime.utcnow().isoformat()}"
        subprocess.run(
            [
                "git",
                "commit",
                "--allow-empty",
                "-m",
                msg,
            ],
            check=True,
        )
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as exc:
        log.error("git backup failed", exc_info=exc)
        raise
    log.info("backed up %d tables", len(paths))


def restore_from_github() -> int:
    """Pull latest backup files from git and restore them into the database.

    Returns the number of tables restored.
    """
    subprocess.run(["git", "pull"], check=False)
    if not db.conn or not BACKUP_DIR.exists():  # type: ignore[attr-defined]
        return 0
    restored = 0
    for file in BACKUP_DIR.glob("*.json"):
        table = file.stem
        coll = db[table]
        try:
            with open(file) as f:
                rows = json.load(f)
        except Exception:
            continue
        for row in rows:
            coll.replace_one({"_id": row.get("_id")}, row, upsert=True)
        restored += 1
    log.info("restored %d tables", restored)
    return restored
