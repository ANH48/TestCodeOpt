from optibot.article_export import ArticleDoc
from optibot.sync_planner import RemoteFile, plan_sync


def doc(article_id: str, content_hash: str) -> ArticleDoc:
    return ArticleDoc(article_id, f"{article_id}.md", f"https://x/{article_id}", "# t", content_hash)


def test_new_changed_unchanged_and_deleted_articles():
    docs = [doc("1", "same"), doc("2", "new-hash"), doc("3", "h3")]
    remote = [RemoteFile("f1", "1", "same"), RemoteFile("f2", "2", "old-hash"), RemoteFile("f9", "9", "h9")]

    plan = plan_sync(docs, remote)

    assert [d.article_id for d in plan.skipped] == ["1"]
    assert [(d.article_id, r.remote_id) for d, r in plan.to_update] == [("2", "f2")]
    assert [d.article_id for d in plan.to_add] == ["3"]
    assert [r.remote_id for r in plan.to_remove] == ["f9"]


def test_duplicate_remote_files_are_cleaned_up():
    plan = plan_sync([doc("1", "h")], [RemoteFile("a", "1", "h"), RemoteFile("b", "1", "h")])
    assert len(plan.skipped) == 1
    assert [r.remote_id for r in plan.to_remove] == ["b"]


def test_failed_ingestion_is_reuploaded():
    # list_remote_files gives failed files an empty hash
    plan = plan_sync([doc("1", "h")], [RemoteFile("a", "1", "")])
    assert len(plan.to_update) == 1


def test_first_run_adds_everything():
    plan = plan_sync([doc("1", "a"), doc("2", "b")], [])
    assert len(plan.to_add) == 2 and not plan.to_update and not plan.to_remove


def test_articles_that_failed_to_convert_keep_their_stored_copy():
    plan = plan_sync([], [RemoteFile("f1", "1", "h")], protected_ids={"1"})
    assert not plan.to_remove


def test_partial_scrape_keeps_orphans_but_still_drops_duplicates():
    remote = [RemoteFile("a", "1", "h"), RemoteFile("b", "1", "h"), RemoteFile("c", "2", "h")]
    plan = plan_sync([doc("1", "h")], remote, remove_orphans=False)
    assert [r.remote_id for r in plan.to_remove] == ["b"]
    assert plan.orphans_kept == 1


def test_duplicate_keeps_the_completed_copy():
    remote = [RemoteFile("failed", "1", ""), RemoteFile("good", "1", "h")]
    plan = plan_sync([doc("1", "h")], remote)
    assert len(plan.skipped) == 1
    assert [r.remote_id for r in plan.to_remove] == ["failed"]
