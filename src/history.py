import json
from pathlib import Path


def _path(site_name: str, directory: str = "history") -> Path:
    safe_name = "".join(char if char.isalnum() else "_" for char in site_name)
    return Path(directory) / f"{safe_name}.json"


def find_new_notices(site_name: str, notices: list[dict], directory: str = "history") -> tuple[bool, list[dict]]:
    path = _path(site_name, directory)
    if not path.exists():
        return True, []
    previous = json.loads(path.read_text(encoding="utf-8"))
    known_titles = {notice.get("title") for notice in previous}
    return False, [notice for notice in notices if notice.get("title") not in known_titles]


def save_history(site_name: str, notices: list[dict], directory: str = "history") -> None:
    path = _path(site_name, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notices, ensure_ascii=False, indent=2), encoding="utf-8")
