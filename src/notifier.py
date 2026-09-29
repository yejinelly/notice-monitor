import base64
import os
from collections import defaultdict
from datetime import datetime
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
KST = ZoneInfo("Asia/Seoul")


def _service():
    load_dotenv()
    credentials_path = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
    token_path = os.environ.get("GMAIL_TOKEN_PATH", "token.json")
    credentials = Credentials.from_authorized_user_file(token_path, SCOPES) if os.path.exists(token_path) else None
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            credentials = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES).run_local_server(port=0)
        with open(token_path, "w") as file:
            file.write(credentials.to_json())
    return build("gmail", "v1", credentials=credentials)


def send_notification(receiver: str, notices: list[dict]) -> bool:
    """Send from the operator's dedicated Notice Monitor Gmail account."""
    if not notices:
        return False
    grouped = defaultdict(list)
    for notice in notices:
        grouped[notice.get("site_name") or "등록한 공지 채널"].append(notice)

    found_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = [
        "관심 키워드와 관련된 새로운 공지가 올라왔습니다.",
        "",
        f"발견 시각: {found_at}",
        f"총 {len(notices)}건의 새 공지",
        "",
        "=" * 58,
        "",
    ]
    for site_name, site_notices in grouped.items():
        lines.extend([f"📌 [{site_name}] - {len(site_notices)}건", "-" * 28, ""])
        for index, notice in enumerate(site_notices, 1):
            lines.extend([
                f"[{index}] {notice['title']}",
                f"날짜: {notice.get('date') or '-'}",
                f"링크: {notice['link']}",
                "",
            ])
    lines.extend(["=" * 58, "이 메일은 Notice Monitor Agent가 자동으로 발송했습니다."])
    message = MIMEText("\n".join(lines), "plain", "utf-8")
    message["To"] = receiver
    message["Subject"] = f"🔔 새 관심 공지 {len(notices)}건"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    _service().users().messages().send(userId="me", body={"raw": raw}).execute()
    return True


def send_registration_confirmation(receiver: str, site_name: str, matched_count: int) -> bool:
    """Confirm that a new subscription's initial baseline was saved."""
    lines = [
        "Notice Monitor Agent 알림 등록이 완료되었습니다.",
        "",
        f"추적 채널: {site_name}",
        f"현재 기준 공지: {matched_count}건",
        "",
        "현재 공지는 기준 목록으로 저장했습니다. 다음 정기 확인부터 새로 올라온 관심 공지만 이메일로 알려드립니다.",
        "이 메일은 Notice Monitor Agent가 자동으로 발송했습니다.",
    ]
    message = MIMEText("\n".join(lines), "plain", "utf-8")
    message["To"] = receiver
    message["Subject"] = f"✅ Notice Monitor 알림 등록 완료 · {site_name}"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    _service().users().messages().send(userId="me", body={"raw": raw}).execute()
    return True
