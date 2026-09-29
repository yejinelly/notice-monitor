from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Read and minimally validate a user's YAML configuration."""
    with Path(path).open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not config.get("receiver_email"):
        raise ValueError("config.yaml에 receiver_email을 입력하세요.")
    if not config.get("sites"):
        raise ValueError("config.yaml에 하나 이상의 sites 항목을 추가하세요.")
    return config
