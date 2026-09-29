def match_keywords(notice: dict, keywords: dict | None) -> list[str]:
    """Return matched keywords; an empty list means the notice is excluded."""
    keywords = keywords or {}
    required = keywords.get("all", [])
    optional = keywords.get("any", [])
    text = f"{notice.get('title', '')} {notice.get('body', '')}".lower()

    if required and not all(keyword.lower() in text for keyword in required):
        return []
    if optional and not any(keyword.lower() in text for keyword in optional):
        return []
    return required + [keyword for keyword in optional if keyword.lower() in text]


def filter_notices(notices: list[dict], keywords: dict | None) -> list[dict]:
    filtered = []
    for notice in notices:
        matched = match_keywords(notice, keywords)
        # With no keyword rule, all notices pass.
        if matched or not (keywords or {}).get("all", []) and not (keywords or {}).get("any", []):
            filtered.append({**notice, "matched_keywords": matched or ["전체"]})
    return filtered
