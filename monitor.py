#!/usr/bin/env python3
"""Check configured notice sources and optionally send a Gmail notification."""
import argparse

from src.config import load_config
from src.fetchers import fetch_notices
from src.filters import filter_notices
from src.history import find_new_notices, save_history
from src.notifier import send_notification


def check(config: dict, update_history: bool = True) -> tuple[list[dict], list[str]]:
    """Return new notices and a human-readable execution log."""
    new_notices, log = [], []
    for site in config["sites"]:
        name = site["name"]
        try:
            fetched = fetch_notices(site)
            matched = filter_notices(fetched, site.get("keywords"))
            first_run, new = find_new_notices(name, matched)
            for notice in new:
                notice["site_name"] = name
            if update_history:
                save_history(name, matched)
            if first_run:
                log.append(f"{name}: 첫 실행 — {len(matched)}건을 기준 목록으로 저장했습니다.")
            else:
                log.append(f"{name}: {len(fetched)}건 수집, {len(matched)}건 매칭, 새 공지 {len(new)}건")
            new_notices.extend(new)
        except Exception as error:
            log.append(f"{name}: 수집 실패 — {error}")
    return new_notices, log


def main() -> None:
    parser = argparse.ArgumentParser(description="관심 공지 모니터")
    parser.add_argument("--config", default="config.yaml", help="설정 파일 경로 (기본: config.yaml)")
    parser.add_argument("--send", action="store_true", help="새 공지가 있으면 Gmail 알림 전송")
    args = parser.parse_args()

    config = load_config(args.config)
    notices, log = check(config)
    print("\n".join(log))
    if args.send and notices:
        send_notification(config["receiver_email"], notices)
        print(f"이메일 알림을 {config['receiver_email']}로 보냈습니다.")
    elif not notices:
        print("새 공지가 없습니다.")
    else:
        print(f"새 공지 {len(notices)}건을 찾았습니다. --send 옵션으로 이메일을 보낼 수 있습니다.")


if __name__ == "__main__":
    main()
