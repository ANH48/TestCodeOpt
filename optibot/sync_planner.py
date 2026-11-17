"""Decides which documents to add, update, skip or remove. Pure logic, no I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AbstractSet, Dict, List, Sequence, Tuple

from optibot.article_export import ArticleDoc


@dataclass(frozen=True)
class RemoteFile:
    remote_id: str
    article_id: str
    content_hash: str


@dataclass
class SyncPlan:
    to_add: List[ArticleDoc] = field(default_factory=list)
    to_update: List[Tuple[ArticleDoc, RemoteFile]] = field(default_factory=list)
    skipped: List[ArticleDoc] = field(default_factory=list)
    to_remove: List[RemoteFile] = field(default_factory=list)
    orphans_kept: int = 0


def plan_sync(
    docs: Sequence[ArticleDoc],
    remote_files: Sequence[RemoteFile],
    protected_ids: AbstractSet[str] = frozenset(),
    remove_orphans: bool = True,
) -> SyncPlan:
    """`protected_ids`: articles that were scraped but failed to convert, so their old copy stays.
    `remove_orphans`: False when the scrape is known to be partial (e.g. MAX_ARTICLES)."""
    plan = SyncPlan()
    remote_by_article: Dict[str, RemoteFile] = {}
    # Completed copies first, so a duplicate left by a failed ingestion is the one dropped.
    for remote in sorted(remote_files, key=lambda r: r.content_hash == ""):
        if remote.article_id in remote_by_article:
            plan.to_remove.append(remote)  # duplicate from an interrupted earlier run
        else:
            remote_by_article[remote.article_id] = remote

    for doc in docs:
        remote = remote_by_article.pop(doc.article_id, None)
        if remote is None:
            plan.to_add.append(doc)
        elif remote.content_hash != doc.content_hash:
            plan.to_update.append((doc, remote))
        else:
            plan.skipped.append(doc)

    # Whatever is left was unpublished or deleted on the Help Center.
    orphans = [r for r in remote_by_article.values() if r.article_id not in protected_ids]
    if remove_orphans:
        plan.to_remove.extend(orphans)
    else:
        plan.orphans_kept = len(orphans)
    return plan
