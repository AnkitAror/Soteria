"""Shared Gemini client for chat/orchestration and chat/rag.

generate_content/embed_content wrap the raw client so every call site's
usage is recorded in one place (chat/usage.py) rather than each of the four
call sites having to remember to do it themselves.
"""

from functools import lru_cache

from google import genai
from google.genai import types

from soteria.chat.usage import record_usage
from soteria.core.config import get_settings


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def generate_content(
    *, model: str, contents: types.ContentListUnionDict, config: types.GenerateContentConfig
) -> types.GenerateContentResponse:
    response = get_client().models.generate_content(model=model, contents=contents, config=config)
    record_usage()
    return response


def embed_content(
    *, model: str, contents: types.ContentListUnionDict, config: types.EmbedContentConfig
) -> types.EmbedContentResponse:
    response = get_client().models.embed_content(model=model, contents=contents, config=config)
    record_usage()
    return response
