from datetime import datetime
import re
from urllib.parse import urljoin, urlparse
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


_CHALLENGE_HEX = re.compile(r'toNumbers\("([0-9a-f]+)"\)')
_CHALLENGE_REDIRECT = re.compile(r'location\.href="([^"]+)"')


def _unpad(data: bytes) -> bytes:
    """Mirror slowAES.unpadBytesOut so the cookie matches the browser's."""
    pad_byte, pad_count = -1, 0
    for i in range(len(data) - 1, len(data) - 18, -1):
        if i < 0 or data[i] > 16:
            break
        if pad_byte == -1:
            pad_byte = data[i]
        if data[i] != pad_byte:
            pad_count = 0
            break
        pad_count += 1
        if pad_count == pad_byte:
            break
    return data[:len(data) - pad_count] if pad_count else data


def _solve_cookie_challenge(session: requests.Session, response: requests.Response) -> requests.Response:
    """Some hosting providers answer cloud IPs with a JavaScript page that sets
    an AES-derived cookie and reloads. Compute the same cookie and reload."""
    text = response.text
    if "slowAES.decrypt" not in text or len(text) > 5000:
        return response
    values = _CHALLENGE_HEX.findall(text)
    cookie = re.search(r'document\.cookie="(\w+)="', text)
    redirect = _CHALLENGE_REDIRECT.search(text)
    if len(values) < 3 or not cookie or not redirect:
        return response
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    key, iv, cipher_text = (bytes.fromhex(value) for value in values[:3])
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plain = _unpad(decryptor.update(cipher_text) + decryptor.finalize())
    host = urlparse(response.url).hostname
    session.cookies.set(cookie.group(1), plain.hex(), domain=host, path="/")
    retry = session.get(urljoin(response.url, redirect.group(1)), headers=HEADERS, timeout=20)
    retry.raise_for_status()
    return retry


def _get(url: str) -> requests.Response:
    session = requests.Session()
    response = session.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return _solve_cookie_challenge(session, response)


def _notice(title: str, link: str, date: str = "", body: str = "") -> dict:
    return {
        "title": title.strip(),
        "link": link.strip(),
        "date": date.strip(),
        "body": body.strip(),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def fetch_rss(site: dict) -> list[dict]:
    response = _get(site["url"])
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
    response = _get(site["url"])
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
        elif not soup.select("tr"):
            # WordPress KBoard boards list notices as <li> rows, not a table.
            items = soup.select("ul.board_body > li")

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
        response = _get(site["url"])
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
