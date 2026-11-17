"""Counts the chunks Gemini's white-space chunking produces for a document.

The File Search API does not report chunk counts. With `white_space_config` a token
is a whitespace-separated word, so the same sliding window can be reproduced locally.
"""
from __future__ import annotations

import math


def count_chunks(text: str, max_tokens: int, overlap_tokens: int) -> int:
    tokens = len(text.split())
    if tokens <= max_tokens:
        return 1 if tokens else 0
    step = max_tokens - overlap_tokens
    return 1 + math.ceil((tokens - max_tokens) / step)
