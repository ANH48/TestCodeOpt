"""Asks OptiBot a question from the command line, using the same system prompt as AI Studio.

Usage: python ask.py "How do I add a YouTube video?"
"""
from __future__ import annotations

import os
import sys

from google.genai import types

from optibot.config import load_settings
from optibot.file_search_store_sync import get_or_create_store, make_client

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def ask(question: str) -> str:
    settings = load_settings()
    client = make_client(settings.gemini_api_key)
    store = get_or_create_store(client, settings.store_display_name, settings.store_name)
    response = client.models.generate_content(
        model=MODEL,
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store]))],
        ),
    )
    return response.text or ""


if __name__ == "__main__":
    print(ask(" ".join(sys.argv[1:]) or "How do I add a YouTube video?"))
