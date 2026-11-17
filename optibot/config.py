"""Runtime settings, read once from environment variables (.env supported)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    help_center_url: str
    locale: str
    max_articles: int
    store_display_name: str
    store_name: str
    output_dir: str
    chunk_max_tokens: int
    chunk_overlap_tokens: int
    upload_workers: int
    allow_mass_delete: bool

    def validate(self) -> None:
        # Failing here beats a 400 error on every upload.
        if self.chunk_max_tokens < 50:
            raise RuntimeError("CHUNK_MAX_TOKENS must be at least 50.")
        if not 0 <= self.chunk_overlap_tokens <= self.chunk_max_tokens // 2:
            raise RuntimeError("CHUNK_OVERLAP_TOKENS must be between 0 and half of CHUNK_MAX_TOKENS.")
        if self.upload_workers < 1 or self.max_articles < 0:
            raise RuntimeError("UPLOAD_WORKERS must be >= 1 and MAX_ARTICLES >= 0.")


def load_settings() -> Settings:
    load_dotenv()
    # The take-home spec runs the image with `-e API_KEY=...`, so accept that name too.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY") or ""
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY (or API_KEY) environment variable.")
    settings = Settings(
        gemini_api_key=api_key,
        help_center_url=os.getenv("HELP_CENTER_URL", "https://support.optisigns.com").rstrip("/"),
        locale=os.getenv("HELP_CENTER_LOCALE", "en-us"),
        max_articles=int(os.getenv("MAX_ARTICLES", "0")),  # 0 = every article
        store_display_name=os.getenv("FILE_SEARCH_STORE_DISPLAY_NAME", "optibot-help-center"),
        store_name=os.getenv("FILE_SEARCH_STORE_NAME", ""),  # e.g. fileSearchStores/abc123
        output_dir=os.getenv("OUTPUT_DIR", "articles"),
        chunk_max_tokens=int(os.getenv("CHUNK_MAX_TOKENS", "400")),
        chunk_overlap_tokens=int(os.getenv("CHUNK_OVERLAP_TOKENS", "100")),
        upload_workers=int(os.getenv("UPLOAD_WORKERS", "4")),
        allow_mass_delete=os.getenv("ALLOW_MASS_DELETE", "") == "1",
    )
    settings.validate()
    return settings
