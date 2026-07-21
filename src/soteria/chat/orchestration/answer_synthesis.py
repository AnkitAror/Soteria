"""Turns SQL results + retrieved context into a natural-language answer.

Uses structured output so citations are a typed part of the response rather
than something parsed out of prose. The model is only shown the specific
rows/items it's allowed to cite, and any citation referencing something
outside that set is dropped in _sanitize_citations rather than trusted.
"""

import json
from decimal import Decimal

from google.genai import types
from pydantic import BaseModel

from soteria.chat.gemini_client import generate_content
from soteria.chat.types import AnswerWithCitations, Citation, RetrievedItem
from soteria.core.config import get_settings

_SYSTEM_INSTRUCTION = """
You answer a user's question about their personal finances using only the
SQL query results and retrieved context items provided to you. Be concise
and specific (use real numbers/dates from the data).

For citations:
- If you used the SQL results, include exactly one citation with
  type "sql_result", ref_id null, and a label summarizing what was queried
  (e.g. "42 transactions, Jun 1-30").
- For each retrieved context item you actually relied on, include a citation
  with its type and exact ref_id as given to you.
- Never cite an item that wasn't provided to you. If nothing supports the
  answer, return an empty citations list and say so in the answer.
""".strip()


class _CitationOut(BaseModel):
    type: str
    ref_id: str | None
    label: str
    detail: str


class _AnswerOut(BaseModel):
    answer: str
    citations: list[_CitationOut]


def _row_default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def synthesize_answer(
    question: str,
    sql_rows: list[dict],
    retrieved_context: list[RetrievedItem],
) -> AnswerWithCitations:
    context_ids = {item.object_id for item in retrieved_context}

    prompt_parts = [f"Question: {question}"]
    if sql_rows:
        prompt_parts.append(
            "SQL results (JSON rows):\n" + json.dumps(sql_rows, default=_row_default)[:8000]
        )
    if retrieved_context:
        items_text = "\n".join(
            f"- [{item.object_type}:{item.object_id}] {item.content}" for item in retrieved_context
        )
        prompt_parts.append(f"Retrieved context items:\n{items_text}")
    if not sql_rows and not retrieved_context:
        prompt_parts.append("No data or context was retrieved for this question.")

    response = generate_content(
        model=get_settings().gemini_chat_model,
        contents="\n\n".join(prompt_parts),
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_AnswerOut,
            temperature=0.0,
        ),
    )
    parsed = response.parsed
    if not isinstance(parsed, _AnswerOut):
        return AnswerWithCitations(answer="I couldn't generate an answer just now.", citations=[])

    citations = _sanitize_citations(parsed.citations, context_ids)
    return AnswerWithCitations(answer=parsed.answer, citations=citations)


def _sanitize_citations(raw: list[_CitationOut], context_ids: set[str]) -> list[Citation]:
    citations = []
    for c in raw:
        if c.type == "sql_result":
            citations.append(Citation(type=c.type, ref_id=None, label=c.label, detail=c.detail))
        elif c.ref_id in context_ids:
            citations.append(Citation(type=c.type, ref_id=c.ref_id, label=c.label, detail=c.detail))
        # else: hallucinated reference to something never provided -- dropped.
    return citations
