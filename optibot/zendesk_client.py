"""Reads published articles from the public Zendesk Help Center API."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator, List

import requests

log = logging.getLogger(__name__)

PAGE_SIZE = 100
MAX_RETRIES = 4


@dataclass(frozen=True)
class Article:
    id: int
    title: str
    html_url: str
    updated_at: str
    body_html: str


def _get_json(session: requests.Session, url: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 429:  # rate limited: honour Retry-After
                wait = int(resp.headers.get("Retry-After", "5"))
                log.warning("Rate limited by Zendesk, waiting %ss", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            log.warning("Zendesk request failed (%s), retry %d/%d", exc, attempt, MAX_RETRIES)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Zendesk request kept failing: {url}")


def _iter_articles(base_url: str, locale: str) -> Iterator[Article]:
    url = f"{base_url}/api/v2/help_center/{locale}/articles.json?per_page={PAGE_SIZE}&sort_by=position"
    with requests.Session() as session:
        session.headers["User-Agent"] = "optibot-sync/1.0"
        while url:
            data = _get_json(session, url)
            for raw in data.get("articles", []):
                # Drafts and empty bodies are not useful knowledge for the bot.
                if raw.get("draft") or not raw.get("body"):
                    continue
                yield Article(
                    id=raw["id"],
                    title=raw["title"].strip(),
                    html_url=raw["html_url"],
                    updated_at=raw["updated_at"],
                    body_html=raw["body"],
                )
            url = data.get("next_page")


def fetch_articles(base_url: str, locale: str, limit: int = 0) -> List[Article]:
    """Return published articles; `limit` 0 means no limit."""
    articles: List[Article] = []
    for article in _iter_articles(base_url, locale):
        articles.append(article)
        if limit and len(articles) >= limit:
            break
    log.info("Fetched %d articles from %s", len(articles), base_url)
    return articles
