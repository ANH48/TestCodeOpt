"""Builds Markdown documents from articles and writes them to disk as <slug>.md."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from optibot.markdown_converter import build_article_markdown
from optibot.zendesk_client import Article

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArticleDoc:
    article_id: str
    filename: str
    url: str
    markdown: str
    content_hash: str


def slug_from_url(url: str) -> str:
    """`.../articles/360041435013-How-to-Add-a-YouTube-Video` -> `360041435013-how-to-add-a-youtube-video`."""
    last = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "-", last.lower()).strip("-")


def build_doc(article: Article) -> ArticleDoc:
    markdown = build_article_markdown(article.title, article.html_url, article.body_html)
    return ArticleDoc(
        article_id=str(article.id),
        filename=f"{slug_from_url(article.html_url)}.md",
        url=article.html_url,
        markdown=markdown,
        # Hashing the rendered Markdown (not Zendesk's updated_at) means converter
        # improvements also count as updates, and cosmetic Zendesk saves do not.
        content_hash=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    )


def build_docs(articles: Iterable[Article]) -> Tuple[List[ArticleDoc], List[str]]:
    """Return converted docs and the IDs of articles that failed to convert."""
    docs, failed_ids = [], []
    for article in articles:
        try:
            docs.append(build_doc(article))
        except Exception:  # one malformed article must not stop the whole run
            log.exception("Could not convert article %s (%s)", article.id, article.html_url)
            failed_ids.append(str(article.id))
    return docs, failed_ids


def write_docs(docs: Iterable[ArticleDoc], output_dir: str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    wanted = set()
    for doc in docs:
        (out / doc.filename).write_text(doc.markdown, encoding="utf-8")
        wanted.add(doc.filename)
    for stale in out.glob("*.md"):  # articles removed or renamed on Zendesk
        if stale.name not in wanted:
            stale.unlink()
    log.info("Wrote %d Markdown files to %s", len(wanted), out)
    return out
