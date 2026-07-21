"""NL -> SQL generation against the chat-safe views.

The model is only ever shown the introspected view schema (schema_introspection
.py) -- never the real base tables -- and is told the views are already
scoped to the current user, so it never needs (and shouldn't attempt) a
user_id filter of its own. Whatever it produces still has to pass
sql_safety.validate_sql before it's ever executed.
"""

from google.genai import types
from pydantic import BaseModel

from soteria.chat.gemini_client import get_client
from soteria.chat.types import ChatTurn
from soteria.core.config import get_settings

_SYSTEM_INSTRUCTION_TEMPLATE = """
You translate a user's question about their personal finances into a single
read-only PostgreSQL SELECT statement.

Rules:
- Query only these views, and only the columns listed for each:
{schema}
- Every view is already scoped to the current user -- do not filter by
  user_id, and do not attempt to query any table not listed above.
- Output exactly one SELECT statement. No writes, no DDL, no multiple
  statements, no comments.
- Always include a LIMIT (500 or fewer).
- If the question cannot be answered from these views, respond with an
  empty string.
""".strip()


class _SqlResponse(BaseModel):
    sql: str


def generate_sql(question: str, schema: str, history: list[ChatTurn]) -> str:
    contents = [f"{turn.role}: {turn.content}" for turn in history] + [f"user: {question}"]

    response = get_client().models.generate_content(
        model=get_settings().gemini_chat_model,
        contents="\n".join(contents),
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION_TEMPLATE.format(schema=schema),
            response_mime_type="application/json",
            response_schema=_SqlResponse,
            temperature=0.0,
        ),
    )
    parsed = response.parsed
    return parsed.sql.strip() if isinstance(parsed, _SqlResponse) else ""
