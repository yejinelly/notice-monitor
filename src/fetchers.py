from datetime import datetime
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "NoticeMonitorAgent/1.0 (+https://github.com/)"}


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
    notices = []
    seen = set()
    for item in soup.select(item_selector):
        title_element = item.select_one(title_selector)
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
