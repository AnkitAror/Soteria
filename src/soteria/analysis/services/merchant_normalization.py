"""Merchant name normalization: map noisy transaction strings to a canonical name.

E.g. "AMZN Mktp US*X81..." -> "Amazon".
"""

import re

_KNOWN_MERCHANTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"AMZN\s*MKTP", re.IGNORECASE), "Amazon"),
    (re.compile(r"\bAMAZON\b", re.IGNORECASE), "Amazon"),
    (re.compile(r"\bUBER\b", re.IGNORECASE), "Uber"),
    (re.compile(r"STARBUCKS", re.IGNORECASE), "Starbucks"),
    (re.compile(r"MCDONALD", re.IGNORECASE), "McDonald's"),
    (re.compile(r"WAL-?MART", re.IGNORECASE), "Walmart"),
    (re.compile(r"\bTARGET\b", re.IGNORECASE), "Target"),
    (re.compile(r"\bKFC\b", re.IGNORECASE), "KFC"),
]


def normalize_merchant(raw: str) -> str:
    for pattern, canonical in _KNOWN_MERCHANTS:
        if pattern.search(raw):
            return canonical
    return _fallback_clean(raw)


def _fallback_clean(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"\*.*$", "", text)  # drop trailing "*XXXX" reference/order suffixes
    text = re.sub(r"#\d+.*$", "", text)  # drop trailing store numbers like "#1234"
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text.title() if text else raw.strip()
