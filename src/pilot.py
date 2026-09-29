"""Rules for the time-limited public Notice Monitor pilot."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DEFAULT_END_AT = "2026-10-30T23:59:59+09:00"


def end_at() -> datetime:
    """Return the public-pilot end time, configurable only by the operator."""
    value = os.environ.get("PILOT_END_AT", DEFAULT_END_AT)
    return datetime.fromisoformat(value).astimezone(KST)


def is_active(now: datetime | None = None) -> bool:
    current = now.astimezone(KST) if now else datetime.now(KST)
    return current <= end_at()


def end_message() -> str:
    return f"공개 파일럿은 {end_at().strftime('%Y년 %-m월 %-d일')}에 종료되었습니다."
