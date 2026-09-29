#!/usr/bin/env python3
"""Run by the existing scheduler to check all public subscriptions."""
import argparse
from collections import defaultdict

from src.database import due_subscriptions, is_first_check, record_check
from src.fetchers import fetch_notices
from src.filters import filter_notices
from src.notifier import send_notification


def run(send: bool = True, force: bool = False) -> list[str]:
    log, notices_by_email = [], defaultdict(list)
    for subscription in due_subscriptions(force=force):
        try:
            site = {
                "name": subscription["site_name"], "url": subscription["site_url"],
                "type": subscription["site_type"], "selectors": subscription["selectors"],
            }
            fetched = fetch_notices(site)
            matched = filter_notices(fetched, subscription["keywords"])
            first_check = is_first_check(subscription["id"])
            fresh = record_check(subscription["id"], matched)
            if first_check:
                log.append(f"{subscription['site_name']} ({subscription['email']}): 첫 확인, {len(matched)}건 기준 저장")
                continue
            for notice in fresh:
                notice["site_name"] = subscription["site_name"]
            notices_by_email[subscription["email"]].extend(fresh)
            log.append(f"{subscription['site_name']} ({subscription['email']}): {len(fresh)}건 새 공지")
        except Exception as error:
            log.append(f"{subscription['site_name']} ({subscription['email']}): 실패 — {error}")

    if send:
        for email, notices in notices_by_email.items():
            if notices:
                send_notification(email, notices)
                log.append(f"{email}: {len(notices)}건 이메일 발송")
    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="공개 Notice Monitor Agent 정기 실행기")
    parser.add_argument("--no-send", action="store_true", help="이메일을 발송하지 않고 결과만 확인")
    parser.add_argument("--force", action="store_true", help="설정한 시간을 무시하고 모든 구독을 확인")
    args = parser.parse_args()
    print("\n".join(run(send=not args.no_send, force=args.force)) or "실행할 구독이 없습니다.")
