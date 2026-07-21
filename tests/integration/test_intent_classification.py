"""Integration test for chat/orchestration/intent_classification -- makes a
real Gemini call, so it's skipped unless GEMINI_API_KEY is configured
(mirrors the DATABASE_URL guard in tests/integration/conftest.py).
"""

import pytest

from soteria.chat.orchestration.intent_classification import classify_intent
from soteria.core.config import get_settings


@pytest.fixture(autouse=True)
def _require_gemini_key() -> None:
    if not get_settings().gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not configured -- set it to run this test")


def test_plain_data_question_does_not_need_context() -> None:
    intent = classify_intent("How much did I spend on dining last month?")

    assert intent.needs_sql
    assert not intent.needs_context


def test_explanation_question_needs_context() -> None:
    intent = classify_intent("Why did my spending spike this month?")

    assert intent.needs_context


def test_general_chit_chat_needs_neither() -> None:
    intent = classify_intent("Hi there, how are you?")

    assert not intent.needs_sql
    assert not intent.needs_context
