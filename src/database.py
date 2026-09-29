"""Persistent subscription and deduplication storage for the public agent."""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(os.environ.get("DATABASE_PATH", "data/notice_monitor.db"))


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL,
            site_name TEXT NOT NULL,
            site_url TEXT NOT NULL,
            site_type TEXT NOT NULL,
            keywords_json TEXT NOT NULL,
            selectors_json TEXT NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'daily',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_checked_at TEXT,
            UNIQUE(email, site_url)
        );
        CREATE TABLE IF NOT EXISTS seen_notices (
            subscription_id INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            PRIMARY KEY(subscription_id, fingerprint),
            FOREIGN KEY(subscription_id) REFERENCES subscriptions(id)
        );
        """
    )
    return connection


def save_subscription(subscription: dict, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Create or update a user's subscription for a site."""
    now = datetime.now().isoformat(timespec="seconds")
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO subscriptions
                (email, site_name, site_url, site_type, keywords_json, selectors_json, frequency, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email, site_url) DO UPDATE SET
                site_name=excluded.site_name,
                site_type=excluded.site_type,
                keywords_json=excluded.keywords_json,
                selectors_json=excluded.selectors_json,
                frequency=excluded.frequency,
                active=1
            """,
            (
                subscription["email"],
                subscription["site_name"],
                subscription["site_url"],
                subscription["site_type"],
                json.dumps(subscription.get("keywords", {}), ensure_ascii=False),
                json.dumps(subscription.get("selectors", {}), ensure_ascii=False),
                subscription.get("frequency", "daily"),
                now,
            ),
        )
        row = connection.execute(
            "SELECT id FROM subscriptions WHERE email=? AND site_url=?",
            (subscription["email"], subscription["site_url"]),
        ).fetchone()
    return int(row["id"])


def due_subscriptions(db_path: str | Path = DEFAULT_DB_PATH, force: bool = False) -> list[dict]:
    """Return active subscriptions that should run in the current scheduler pass."""
    now = datetime.now()
    current_run = now.strftime("%Y-%m-%dT%H")
    with connect(db_path) as connection:
        rows = connection.execute("SELECT * FROM subscriptions WHERE active=1 ORDER BY id").fetchall()
    subscriptions = []
    for row in rows:
        scheduled_hours = {
            "schedule_10": {10},
            "schedule_14": {14},
            "schedule_10_14": {10, 14},
            # Existing records from early versions remain usable.
            "daily": {10, 14},
            "every_run": {10, 14},
        }.get(row["frequency"], {10, 14})
        last_checked = row["last_checked_at"] or ""
        if not force and (now.hour not in scheduled_hours or last_checked.startswith(current_run)):
            continue
        subscriptions.append(_decode_subscription(row))
    return subscriptions


def _decode_subscription(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "email": row["email"], "site_name": row["site_name"],
        "site_url": row["site_url"], "site_type": row["site_type"],
        "keywords": json.loads(row["keywords_json"]), "selectors": json.loads(row["selectors_json"]),
        "frequency": row["frequency"], "last_checked_at": row["last_checked_at"],
    }


def is_first_check(subscription_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> bool:
    with connect(db_path) as connection:
        row = connection.execute("SELECT last_checked_at FROM subscriptions WHERE id=?", (subscription_id,)).fetchone()
    return not row or row["last_checked_at"] is None


def record_check(subscription_id: int, notices: list[dict], db_path: str | Path = DEFAULT_DB_PATH) -> list[dict]:
    """Persist seen notices and return only previously unseen items."""
    now = datetime.now().isoformat(timespec="seconds")
    fresh = []
    with connect(db_path) as connection:
        for notice in notices:
            fingerprint = f"{notice.get('title', '')}|{notice.get('link', '')}"
            exists = connection.execute(
                "SELECT 1 FROM seen_notices WHERE subscription_id=? AND fingerprint=?",
                (subscription_id, fingerprint),
            ).fetchone()
            if not exists:
                fresh.append(notice)
                connection.execute(
                    "INSERT INTO seen_notices (subscription_id, fingerprint, title, link, seen_at) VALUES (?, ?, ?, ?, ?)",
                    (subscription_id, fingerprint, notice.get("title", ""), notice.get("link", ""), now),
                )
        connection.execute("UPDATE subscriptions SET last_checked_at=? WHERE id=?", (now, subscription_id))
    return fresh
