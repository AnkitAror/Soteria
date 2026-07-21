"""Shared Gemini client factory for chat/orchestration and chat/rag."""

from functools import lru_cache

from google import genai

from soteria.core.config import get_settings


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)
