"""Transaction categorization: map Plaid's raw category + description to a fixed bucket set.

Not every transaction fits Food/Shopping/Travel/Entertainment/Utilities
(e.g. "Payment", "Transfer, Debit") — those fall back to DEFAULT_CATEGORY
rather than being force-fit into one of the five.
"""

import re

DEFAULT_CATEGORY = "Other"

_CATEGORY_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"food and drink|restaurant|coffee", re.IGNORECASE), "Food"),
    (re.compile(r"\bshops?\b|shopping|merchandise", re.IGNORECASE), "Shopping"),
    (re.compile(r"travel|airlines?|\btaxi\b|rideshare|hotel", re.IGNORECASE), "Travel"),
    (
        re.compile(r"recreation|entertainment|\bgyms?\b|movies?|\barts\b", re.IGNORECASE),
        "Entertainment",
    ),
    (
        re.compile(
            r"utilit(y|ies)|electric|water bill|gas company|internet|telecom", re.IGNORECASE
        ),
        "Utilities",
    ),
]


def categorize_transaction(plaid_category: str | None, description: str) -> str:
    haystack = f"{plaid_category or ''} {description}"
    for pattern, bucket in _CATEGORY_RULES:
        if pattern.search(haystack):
            return bucket
    return DEFAULT_CATEGORY
