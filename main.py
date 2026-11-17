"""Daily job: scrape the Help Center, convert to Markdown, sync the delta to the Gemini File Search store."""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone

from optibot.article_export import build_docs, write_docs
from optibot.chunk_estimator import count_chunks
from optibot.config import load_settings
from optibot.sync_planner import SyncPlan, plan_sync
from optibot.file_search_store_sync import FileSearchStoreSync, get_or_create_store, list_remote_files, make_client
from optibot.zendesk_client import fetch_articles

REPORT_PATH = "run_report.json"

log = logging.getLogger("optibot")

# Removing more than this share of the store in one run looks like a broken scrape, not real deletions.
MASS_DELETE_RATIO = 0.2


def plan_with_delete_guard(settings, docs, conversion_failures, remote) -> SyncPlan:
    full_scrape = settings.max_articles == 0 and bool(docs)
    plan = plan_sync(docs, remote, set(conversion_failures), remove_orphans=full_scrape)
    if not full_scrape:
        log.warning("Partial scrape: keeping %d stored articles that were not fetched", plan.orphans_kept)
    elif len(plan.to_remove) > max(5, MASS_DELETE_RATIO * len(remote)) and not settings.allow_mass_delete:
        plan = plan_sync(docs, remote, set(conversion_failures), remove_orphans=False)
        log.warning(
            "Refusing to delete %d of %d stored articles; set ALLOW_MASS_DELETE=1 if this is intended",
            plan.orphans_kept, len(remote),
        )
    return plan


def run() -> int:
    started = time.monotonic()
    settings = load_settings()

    articles = fetch_articles(settings.help_center_url, settings.locale, settings.max_articles)
    docs, conversion_failures = build_docs(articles)
    write_docs(docs, settings.output_dir)

    client = make_client(settings.gemini_api_key)
    store = get_or_create_store(client, settings.store_display_name, settings.store_name)
    plan = plan_with_delete_guard(settings, docs, conversion_failures, list_remote_files(client, store))
    log.info(
        "Plan for File Search store %s: add=%d update=%d skip=%d remove=%d",
        store, len(plan.to_add), len(plan.to_update), len(plan.skipped), len(plan.to_remove),
    )

    sync = FileSearchStoreSync(
        client, store, settings.chunk_max_tokens, settings.chunk_overlap_tokens, settings.upload_workers
    )
    result = sync.apply(plan)
    result.failed.extend(f"convert:{article_id}" for article_id in conversion_failures)
    chunks = sum(
        count_chunks(d.markdown, settings.chunk_max_tokens, settings.chunk_overlap_tokens) for d in result.uploaded_docs
    )
    store_counts = sync.document_counts()

    report = {
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_seconds": round(time.monotonic() - started, 1),
        "file_search_store": store,
        "articles_scraped": len(articles),
        "added": result.added,
        "updated": result.updated,
        "skipped": result.skipped,
        "removed": result.removed,
        "failed": result.failed,
        "files_embedded": len(result.uploaded_docs),
        "chunks_embedded": chunks,
        "store_documents": store_counts,
    }
    log.info(
        "Done: added=%d updated=%d skipped=%d removed=%d failed=%d | embedded %d files, %d chunks | store now holds %d documents",
        result.added, result.updated, result.skipped, result.removed, len(result.failed),
        len(result.uploaded_docs), chunks, store_counts["active"],
    )
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return 1 if result.failed else 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout
    )
    for noisy in ("httpx", "httpx2", "google_genai"):  # one line per API call is too noisy
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        sys.exit(run())
    except Exception:
        log.exception("Sync job failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
