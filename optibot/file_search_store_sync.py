"""Applies a SyncPlan to a Gemini File Search store via the API."""
from __future__ import annotations

import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import List

from google import genai
from google.genai import types

from optibot.article_export import ArticleDoc
from optibot.sync_planner import RemoteFile, SyncPlan

log = logging.getLogger(__name__)

INGEST_TIMEOUT_SECONDS = 300
POLL_SECONDS = 2
HTTP_TIMEOUT_MS = 120_000


@dataclass
class SyncResult:
    added: int = 0
    updated: int = 0
    skipped: int = 0
    removed: int = 0
    failed: List[str] = field(default_factory=list)
    uploaded_docs: List[ArticleDoc] = field(default_factory=list)


def make_client(api_key: str) -> genai.Client:
    # Free-tier keys hit 429s quickly; let the SDK back off and retry.
    retry = types.HttpRetryOptions(attempts=6, initial_delay=2, max_delay=60, http_status_codes=[429, 500, 503])
    # Without a timeout one dead connection hangs the whole job forever (timeout is in milliseconds).
    return genai.Client(
        api_key=api_key, http_options=types.HttpOptions(retry_options=retry, timeout=HTTP_TIMEOUT_MS)
    )


def get_or_create_store(client: genai.Client, display_name: str, store_name: str = "") -> str:
    """Return the store resource name (`fileSearchStores/...`)."""
    if store_name:
        return client.file_search_stores.get(name=store_name).name
    for store in client.file_search_stores.list():
        if store.display_name == display_name:
            return store.name
    store = client.file_search_stores.create(config={"display_name": display_name})
    log.info("Created File Search store %s (%s)", display_name, store.name)
    return store.name


def list_remote_files(client: genai.Client, store_name: str) -> List[RemoteFile]:
    remote = []
    for doc in client.file_search_stores.documents.list(parent=store_name):
        meta = {m.key: m.string_value for m in doc.custom_metadata or []}
        if "article_id" not in meta:
            continue  # not managed by this job (e.g. uploaded by hand)
        # A failed or unfinished ingestion gets an empty hash so the planner re-uploads it.
        content_hash = meta.get("content_hash", "") if doc.state == types.DocumentState.STATE_ACTIVE else ""
        remote.append(RemoteFile(doc.name, meta["article_id"], content_hash or ""))
    return remote


class FileSearchStoreSync:
    def __init__(self, client: genai.Client, store_name: str, max_tokens: int, overlap_tokens: int, workers: int):
        self.client = client
        self.store_name = store_name
        self.workers = workers
        self.chunking = {"white_space_config": {"max_tokens_per_chunk": max_tokens, "max_overlap_tokens": overlap_tokens}}

    def _upload(self, doc: ArticleDoc) -> bool:
        try:
            op = self.client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=self.store_name,
                file=io.BytesIO(doc.markdown.encode("utf-8")),
                config={
                    "display_name": doc.filename,
                    "mime_type": "text/markdown",
                    "custom_metadata": [
                        {"key": "article_id", "string_value": doc.article_id},
                        {"key": "content_hash", "string_value": doc.content_hash},
                        {"key": "url", "string_value": doc.url},
                    ],
                    "chunking_config": self.chunking,
                },
            )
            deadline = time.monotonic() + INGEST_TIMEOUT_SECONDS
            while not op.done and time.monotonic() < deadline:
                time.sleep(POLL_SECONDS)
                op = self.client.operations.get(op)
            if not op.done or op.error:
                # A late-finishing document is listed with an empty hash next run and replaced.
                raise RuntimeError(f"ingestion {'timed out' if not op.done else 'failed'}: {op.error}")
            return True
        except Exception as exc:
            log.error("Upload failed for %s: %s", doc.filename, exc)
            return False

    def _delete(self, document_name: str) -> bool:
        try:
            # force=True also deletes the document's chunks.
            self.client.file_search_stores.documents.delete(name=document_name, config={"force": True})
            return True
        except Exception as exc:
            log.error("Could not delete %s: %s", document_name, exc)
            return False

    def _replace(self, doc: ArticleDoc, old: RemoteFile) -> bool:
        # Upload first so the article never disappears from the store mid-run.
        # If the old copy cannot be deleted, the next run sees a duplicate and removes it.
        if not self._upload(doc):
            return False
        if not self._delete(old.remote_id):
            log.warning("Old copy %s of %s is still stored; next run will clean it up", old.remote_id, doc.filename)
        return True

    def apply(self, plan: SyncPlan) -> SyncResult:
        result = SyncResult(skipped=len(plan.skipped))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            added = list(pool.map(self._upload, plan.to_add))
            updated = list(pool.map(lambda pair: self._replace(*pair), plan.to_update))
            removed = list(pool.map(lambda r: self._delete(r.remote_id), plan.to_remove))

        update_docs = [doc for doc, _ in plan.to_update]
        for docs, outcomes, kind in ((plan.to_add, added, "added"), (update_docs, updated, "updated")):
            for doc, ok in zip(docs, outcomes):
                if ok:
                    setattr(result, kind, getattr(result, kind) + 1)
                    result.uploaded_docs.append(doc)
                else:
                    result.failed.append(doc.filename)
        for remote, ok in zip(plan.to_remove, removed):
            if ok:
                result.removed += 1
            else:
                result.failed.append(f"remove:{remote.remote_id}")
        return result

    def document_counts(self) -> dict:
        store = self.client.file_search_stores.get(name=self.store_name)
        return {
            "active": int(store.active_documents_count or 0),
            "pending": int(store.pending_documents_count or 0),
            "failed": int(store.failed_documents_count or 0),
        }
