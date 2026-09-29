#!/usr/bin/env python3
"""Run by the existing scheduler to check all public subscriptions."""
import argparse
from collections import defaultdict

from src.database import (
    due_subscriptions,
    fresh_notices,
    is_first_check,
    mark_checked,
    mark_sent,
    save_baseline,
)
from src.fetchers import fetch_notices
from src.filters import filter_notices
from src.notifier import send_notification, send_registration_confirmation
from src.pilot import end_message, is_active


def run(send: bool = True, force: bool = False) -> list[str]:
    if not is_active():
        return [end_message() + " 정기 알림을 실행하지 않습니다."]
    log, notices_by_email, baselines = [], defaultdict(list), []
    for subscription in due_subscriptions(force=force):
        try:
            site = {
                "name": subscription["site_name"], "url": subscription["site_url"],
                "type": subscription["site_type"], "selectors": subscription["selectors"],
            }
            fetched = fetch_notices(site)
            matched = filter_notices(fetched, subscription["keywords"])
            first_check = is_first_check(subscription["id"])
            if first_check:
                if send:
                    baselines.append((subscription, matched))
                    log.append(f"{subscription['site_name']} ({subscription['email']}): 첫 확인 예정, {len(matched)}건 기준 저장")
                else:
                    log.append(f"{subscription['site_name']} ({subscription['email']}): 첫 확인 확인만 함 (--no-send, 저장하지 않음)")
                continue
            fresh = fresh_notices(subscription["id"], matched)
            for notice in fresh:
                notice["site_name"] = subscription["site_name"]
            if fresh:
                notices_by_email[subscription["email"]].append((subscription, fresh))
                log.append(f"{subscription['site_name']} ({subscription['email']}): {len(fresh)}건 새 공지")
            elif send:
                mark_checked(subscription["id"])
                log.append(f"{subscription['site_name']} ({subscription['email']}): 새 공지 없음")
            else:
                log.append(f"{subscription['site_name']} ({subscription['email']}): 새 공지 없음 (--no-send, 저장하지 않음)")
        except Exception as error:
            log.append(f"{subscription['site_name']} ({subscription['email']}): 실패 — {error}")

    if send:
        for subscription, matched in baselines:
            try:
                send_registration_confirmation(subscription["email"], subscription["site_name"], len(matched))
                save_baseline(subscription["id"], matched)
                log.append(f"{subscription['email']}: 등록 확인 이메일 발송")
            except Exception as error:
                log.append(f"{subscription['site_name']} ({subscription['email']}): 등록 확인 이메일 실패 — {error}")
        for email, batches in notices_by_email.items():
            notices = [notice for _, batch in batches for notice in batch]
            try:
                send_notification(email, notices)
                for subscription, batch in batches:
                    mark_sent(subscription["id"], batch)
                log.append(f"{email}: {len(notices)}건 이메일 발송")
            except Exception as error:
                log.append(f"{email}: 이메일 발송 실패 — {error}")
    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="공개 Notice Monitor Agent 정기 실행기")
    parser.add_argument("--no-send", action="store_true", help="이메일을 발송하지 않고 결과만 확인")
    parser.add_argument("--force", action="store_true", help="설정한 시간을 무시하고 모든 구독을 확인")
    args = parser.parse_args()
    print("\n".join(run(send=not args.no_send, force=args.force)) or "실행할 구독이 없습니다.")
