"""Classifies a chat question so pipeline.py can skip work it doesn't need.

Retrieval (embedding the question + a pgvector search) is not free, and most
questions about spending are plain structured lookups that SQL answers
completely on its own -- running RAG on every request would be waste for no
retrieval benefit. This module decides, once per question, whether SQL
generation and/or semantic-context retrieval are actually warranted.
"""

from dataclasses import dataclass
from enum import StrEnum

from google.genai import types
from pydantic import BaseModel

from soteria.chat.gemini_client import generate_content
from soteria.core.config import get_settings

_SYSTEM_INSTRUCTION = """
You classify a user's question to a personal-finance chatbot into exactly
one category:

- DATA_QUERY: a factual question answerable by querying the user's
  transactions/subscriptions/accounts (amounts, dates, categories, totals,
  comparisons). e.g. "how much did I spend on dining last month".
- EXPLAIN_OR_ADVICE: asks why something happened, for an opinion, or for
  advice/context beyond raw numbers. e.g. "why did my spending spike",
  "should I cancel this subscription".
- DATA_QUERY_WITH_CONTEXT: needs both a data lookup and supporting
  explanation/context to answer well.
- GENERAL: greetings, chit-chat, or anything not about the user's finances.

Respond with only the category.
""".strip()


class _IntentCategory(StrEnum):
    DATA_QUERY = "DATA_QUERY"
    EXPLAIN_OR_ADVICE = "EXPLAIN_OR_ADVICE"
    DATA_QUERY_WITH_CONTEXT = "DATA_QUERY_WITH_CONTEXT"
    GENERAL = "GENERAL"


class _IntentResponse(BaseModel):
    category: _IntentCategory


@dataclass(frozen=True)
class Intent:
    needs_sql: bool
    needs_context: bool


_NEEDS_SQL = {_IntentCategory.DATA_QUERY, _IntentCategory.DATA_QUERY_WITH_CONTEXT}
_NEEDS_CONTEXT = {_IntentCategory.EXPLAIN_OR_ADVICE, _IntentCategory.DATA_QUERY_WITH_CONTEXT}


def classify_intent(question: str) -> Intent:
    response = generate_content(
        model=get_settings().gemini_chat_model,
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_IntentResponse,
            temperature=0.0,
        ),
    )
    parsed = response.parsed
    category = parsed.category if isinstance(parsed, _IntentResponse) else _IntentCategory.GENERAL
    return Intent(
        needs_sql=category in _NEEDS_SQL,
        needs_context=category in _NEEDS_CONTEXT,
    )
