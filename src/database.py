"""Supabase-backed subscription and deduplication storage."""
import os
from datetime import datetime

from dotenv import load_dotenv
from supabase import Client, create_client

from src.pilot import KST


def _client() -> Client:
    """Create a server-only client. Never expose this key in browser code."""
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        raise RuntimeError("SUPABASE_URL과 SUPABASE_SECRET_KEY를 설정하세요.")
    return create_client(url, service_key)


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _as_kst(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(KST)


def save_subscription(subscription: dict) -> int:
    """Create or update one recipient's subscription for a site."""
    row = {
        "email": subscription["email"].strip().lower(),
        "site_name": subscription["site_name"],
        "site_url": subscription["site_url"],
        "site_type": subscription.get("site_type", "auto"),
        "keywords_json": subscription.get("keywords", {}),
        "selectors_json": subscription.get("selectors", {}),
        "frequency": subscription.get("frequency", "schedule_10_14"),
        "active": True,
    }
    response = _client().table("subscriptions").upsert(
        row, on_conflict="email,site_url"
    ).execute()
    return int(response.data[0]["id"])


def due_subscriptions(force: bool = False) -> list[dict]:
    """Return active subscriptions whose latest KST schedule slot has passed."""
    now = datetime.now(KST)
    rows = _client().table("subscriptions").select("*").eq("active", True).order("id").execute().data
    due = []
    for row in rows:
        scheduled_hours = {
            "schedule_10": {10},
            "schedule_14": {14},
            "schedule_10_14": {10, 14},
            "daily": {10, 14},
            "every_run": {10, 14},
        }.get(row["frequency"], {10, 14})
        slots = [now.replace(hour=hour, minute=0, second=0, microsecond=0) for hour in scheduled_hours]
        elapsed_slots = [slot for slot in slots if slot <= now]
        latest_slot = max(elapsed_slots) if elapsed_slots else None
        last_checked = row.get("last_checked_at")
        if not force and (latest_slot is None or (last_checked and _as_kst(last_checked) >= latest_slot)):
            continue
        due.append(_decode_subscription(row))
    return due


def _decode_subscription(row: dict) -> dict:
    return {
        "id": row["id"], "email": row["email"], "site_name": row["site_name"],
        "site_url": row["site_url"], "site_type": row["site_type"],
        "keywords": row["keywords_json"], "selectors": row["selectors_json"],
        "frequency": row["frequency"], "last_checked_at": row.get("last_checked_at"),
    }


def is_first_check(subscription_id: int) -> bool:
    response = _client().table("subscriptions").select("last_checked_at").eq("id", subscription_id).single().execute()
    return response.data["last_checked_at"] is None


def fresh_notices(subscription_id: int, notices: list[dict]) -> list[dict]:
    """Return notices not previously sent, without mutating subscription state."""
    client = _client()
    known_rows = client.table("seen_notices").select("fingerprint").eq("subscription_id", subscription_id).execute().data
    known = {row["fingerprint"] for row in known_rows}
    fresh = [notice for notice in notices if f"{notice.get('title', '')}|{notice.get('link', '')}" not in known]
    return fresh


def _save_seen(subscription_id: int, notices: list[dict]) -> None:
    if not notices:
        return
    _client().table("seen_notices").upsert([
        {
            "subscription_id": subscription_id,
            "fingerprint": f"{notice.get('title', '')}|{notice.get('link', '')}",
            "title": notice.get("title", ""),
            "link": notice.get("link", ""),
            "seen_at": _now(),
        }
        for notice in notices
    ], on_conflict="subscription_id,fingerprint").execute()


def mark_checked(subscription_id: int) -> None:
    _client().table("subscriptions").update({"last_checked_at": _now()}).eq("id", subscription_id).execute()


def save_baseline(subscription_id: int, notices: list[dict]) -> None:
    """Save the current list as a baseline without treating it as new mail."""
    _save_seen(subscription_id, notices)
    mark_checked(subscription_id)


def mark_sent(subscription_id: int, notices: list[dict]) -> None:
    """Record notices only after their notification email was sent successfully."""
    _save_seen(subscription_id, notices)
    mark_checked(subscription_id)
