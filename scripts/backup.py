#!/usr/bin/env python3
"""Backup SQLite databases every 6 hours.

Запускается как сервис `backup` в профиле `cron`.
Использует sqlite3.backup() для консистентных снапшотов без остановки БД.
"""

import gzip
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("backup")

# Конфигурация из env
DATA_DIR = Path(os.environ.get("BACKUP_DATA_DIR", "/data/app"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/data/backups"))
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "14"))
BACKUP_INTERVAL_HOURS = int(os.environ.get("BACKUP_INTERVAL_HOURS", "6"))
DB_NAMES = ["university.db", "demo_sessions.sqlite"]


def backup_db(name: str) -> Path | None:
    """Создать снапшот .db через sqlite3.backup(), вернуть путь."""
    src = DATA_DIR / name
    if not src.exists():
        logger.warning("Database %s not found, skipping", src)
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{name.stem}_{timestamp}.db"

    try:
        src_conn = sqlite3.connect(str(src))
        dst_conn = sqlite3.connect(str(dst))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        logger.info("Backup created: %s (%d bytes)", dst, dst.stat().st_size)
        return dst
    except Exception as exc:
        logger.error("Backup failed for %s: %s", name, exc)
        if dst.exists():
            dst.unlink()
        return None


def compress_old(max_age_days: int = 1) -> None:
    """Сжать .db файлы старше max_age_days в .db.gz."""
    now = time.time()
    cutoff = now - max_age_days * 86400

    for f in BACKUP_DIR.iterdir():
        if f.suffix == ".db" and f.stat().st_mtime < cutoff:
            gz_path = f.with_suffix(f"{f.suffix}.gz")
            try:
                with f.open("rb") as src, gzip.open(gz_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                f.unlink()
                logger.info(
                    "Compressed: %s -> %s (%d bytes)",
                    f.name,
                    gz_path.name,
                    gz_path.stat().st_size,
                )
            except Exception as exc:
                logger.error("Compression failed for %s: %s", f, exc)


def cleanup_old() -> None:
    """Удалить файлы старше RETENTION_DAYS."""
    now = time.time()
    cutoff = now - RETENTION_DAYS * 86400

    for f in BACKUP_DIR.iterdir():
        if f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                logger.info("Deleted old backup: %s", f.name)
            except Exception as exc:
                logger.error("Cleanup failed for %s: %s", f, exc)


def run_once() -> None:
    """Один цикл бэкапа."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    for db_name in DB_NAMES:
        backup_db(Path(db_name))

    compress_old()
    cleanup_old()


def main() -> None:
    """Основной цикл: бэкап каждые BACKUP_INTERVAL_HOURS часов."""
    logger.info(
        "Backup service started. Interval: %d hours, retention: %d days",
        BACKUP_INTERVAL_HOURS,
        RETENTION_DAYS,
    )

    # Первый бэкап сразу при старте
    run_once()

    interval_seconds = BACKUP_INTERVAL_HOURS * 3600
    while True:
        logger.info("Sleeping for %d hours...", BACKUP_INTERVAL_HOURS)
        time.sleep(interval_seconds)
        run_once()


if __name__ == "__main__":
    main()
