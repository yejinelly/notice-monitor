from datetime import datetime
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

# Some university boards return an empty layout to an obvious automation user
# agent, especially from cloud-hosted applications. Request the public page in
# the same form as a normal desktop browser; no login or private endpoint is
# used.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _notice(title: str, link: str, date: str = "", body: str = "") -> dict:
    return {
        "title": title.strip(),
        "link": link.strip(),
        "date": date.strip(),
        "body": body.strip(),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_rss(site: dict) -> list[dict]:
    response = requests.get(site["url"], headers=HEADERS, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    notices = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        content = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
        body = BeautifulSoup(content.text or "", "html.parser").get_text(" ", strip=True) if content is not None else ""
        notices.append(_notice(title, item.findtext("link") or "", item.findtext("pubDate") or "", body))
    # Atom feeds use <entry>, <updated>, and an href attribute on <link>.
    for entry in root.findall(".//{*}entry"):
        title = (entry.findtext("{*}title") or "").strip()
        if not title:
            continue
        link_element = next(
            (link for link in entry.findall("{*}link") if link.get("rel", "alternate") == "alternate"),
            None,
        )
        link = link_element.get("href", "") if link_element is not None else ""
        body = entry.findtext("{*}content") or entry.findtext("{*}summary") or ""
        notices.append(_notice(title, link, entry.findtext("{*}published") or entry.findtext("{*}updated") or "", body))
    return notices


def fetch_html(site: dict) -> list[dict]:
    """Fetch a conventional HTML board using CSS selectors supplied by the user."""
    response = requests.get(site["url"], headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    selectors = site.get("selectors", {})
    item_selector = selectors.get("item", "tr")
    title_selector = selectors.get("title", "a")
    date_selector = selectors.get("date", "time, .date")
    # Some university boards use several tables for navigation and layout.
    # Prefer the conventional notice-list table when it is available.
    items = soup.select(item_selector)
    if item_selector == "tr":
        board_items = soup.select("table.basic_board_list tr")
        if board_items:
            items = board_items

    notices = []
    seen = set()
    for item in items:
        title_element = item.select_one("td.left a") or item.select_one(title_selector)
        if not title_element:
            continue
        title = title_element.get_text(" ", strip=True)
        if len(title) < 3 or title in seen:
            continue
        href = title_element.get("href", "")
        if not href:
            continue
        seen.add(title)
        date_element = item.select_one(date_selector)
        date = date_element.get_text(" ", strip=True) if date_element else ""
        if not date:
            # Common university-board markup: writer, date, and view count are
            # separate desktop-only cells, with the date in the second cell.
            metadata_cells = item.select("td.mob_none")
            if len(metadata_cells) >= 2:
                date = metadata_cells[1].get_text(" ", strip=True)
        notices.append(_notice(title, urljoin(site["url"], href), date))
    return notices


def fetch_notices(site: dict) -> list[dict]:
    site_type = site.get("type", "html")
    if site_type == "auto":
        response = requests.get(site["url"], headers=HEADERS, timeout=20)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        opening = response.content.lstrip()[:200].lower()
        if "xml" in content_type or opening.startswith(b"<?xml") or b"<rss" in opening or b"<feed" in opening:
            return fetch_rss(site)
        return fetch_html(site)
    if site_type == "rss":
        return fetch_rss(site)
    if site_type == "html":
        return fetch_html(site)
    raise ValueError(f"지원하지 않는 사이트 유형입니다: {site_type}")
