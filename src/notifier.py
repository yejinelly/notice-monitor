import base64
import os
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


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
    if not notices:
        return False
    lines = [f"새로운 관심 공지 {len(notices)}건을 찾았습니다.", ""]
    for index, notice in enumerate(notices, 1):
        lines.extend([f"[{index}] {notice['title']}", f"날짜: {notice.get('date') or '-'}", f"링크: {notice['link']}", ""])
    message = MIMEText("\n".join(lines), "plain", "utf-8")
    message["To"] = receiver
    message["Subject"] = f"🔔 새 관심 공지 {len(notices)}건"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    _service().users().messages().send(userId="me", body={"raw": raw}).execute()
    return True
