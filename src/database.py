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


def _checked_this_run(value: str | None, current_run: str) -> bool:
    if not value:
        return False
    checked_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return checked_at.astimezone(KST).strftime("%Y-%m-%dT%H") == current_run


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
    """Return active subscriptions that should run in this KST scheduler pass."""
    now = datetime.now(KST)
    current_run = now.strftime("%Y-%m-%dT%H")
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
        if not force and (now.hour not in scheduled_hours or _checked_this_run(row.get("last_checked_at"), current_run)):
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


def record_check(subscription_id: int, notices: list[dict]) -> list[dict]:
    """Persist notices and return only links not previously sent for this subscription."""
    client = _client()
    known_rows = client.table("seen_notices").select("fingerprint").eq("subscription_id", subscription_id).execute().data
    known = {row["fingerprint"] for row in known_rows}
    fresh = [notice for notice in notices if f"{notice.get('title', '')}|{notice.get('link', '')}" not in known]
    if fresh:
        client.table("seen_notices").insert([
            {
                "subscription_id": subscription_id,
                "fingerprint": f"{notice.get('title', '')}|{notice.get('link', '')}",
                "title": notice.get("title", ""),
                "link": notice.get("link", ""),
                "seen_at": _now(),
            }
            for notice in fresh
        ]).execute()
    client.table("subscriptions").update({"last_checked_at": _now()}).eq("id", subscription_id).execute()
    return fresh
