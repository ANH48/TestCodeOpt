from optibot.article_export import build_doc, slug_from_url, write_docs
from optibot.chunk_estimator import count_chunks
from optibot.zendesk_client import Article


def article(body: str) -> Article:
    url = "https://support.optisigns.com/hc/en-us/articles/360041435013-How-to-Add-a-YouTube-Video"
    return Article(360041435013, "How to Add a YouTube Video", url, "2026-01-01T00:00:00Z", body)


def test_slug_from_url():
    assert slug_from_url(article("").html_url) == "360041435013-how-to-add-a-youtube-video"


def test_hash_changes_only_when_content_changes():
    a, b, c = build_doc(article("<p>One</p>")), build_doc(article("<p>One</p>")), build_doc(article("<p>Two</p>"))
    assert a.content_hash == b.content_hash != c.content_hash
    assert a.filename == "360041435013-how-to-add-a-youtube-video.md"


def test_write_docs_removes_stale_files(tmp_path):
    (tmp_path / "old-article.md").write_text("gone")
    write_docs([build_doc(article("<p>Hi</p>"))], str(tmp_path))
    assert [p.name for p in tmp_path.glob("*.md")] == ["360041435013-how-to-add-a-youtube-video.md"]


def test_count_chunks_follows_sliding_window():
    assert count_chunks("", 600, 150) == 0
    assert count_chunks("hello world", 600, 150) == 1
    # 2000 words with a 450-word step: 1 + ceil(1400 / 450) = 5
    assert count_chunks(" a" * 2000, 600, 150) == 5
