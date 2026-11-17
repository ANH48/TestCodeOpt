from optibot.markdown_converter import build_article_markdown, heading_slug, html_to_markdown


def test_headings_lists_and_links_survive():
    html = '<h2 id="h_1">Set Up</h2><ol start="3"><li>Open <a href="/hc/en-us/articles/1">Settings</a></li></ol>'
    md = html_to_markdown(html)
    assert "## Set Up" in md
    assert "3. Open [Settings](/hc/en-us/articles/1)" in md  # relative link kept as-is


def test_toc_anchor_points_to_markdown_heading_slug():
    html = (
        '<ul><li><a href="#WhatYouNeed">What You\'ll Need</a></li></ul>'
        '<p><a name="WhatYouNeed"></a></p><h2 id="h_x">What You\'ll Need</h2>'
    )
    md = html_to_markdown(html)
    assert "[What You'll Need](#what-youll-need)" in md
    assert "## What You'll Need" in md


def test_code_block_is_fenced_and_prism_spans_removed():
    html = '<pre><code><span class="token">curl</span> <span class="punctuation">-X</span> GET</code></pre>'
    md = html_to_markdown(html)
    assert "```\ncurl -X GET\n```" in md
    assert "span" not in md


def test_noise_is_removed_and_video_becomes_link():
    html = (
        '<script>track()</script><style>p{}</style>'
        '<p><span style="color:red">Hello</span></p>'
        '<iframe src="//www.youtube.com/embed/abc"></iframe>'
        '<img src="data:image/png;base64,AAAA">'
    )
    md = html_to_markdown(html)
    assert md.startswith("Hello")
    assert "track()" not in md and "base64" not in md
    assert "[Embedded video](https://www.youtube.com/embed/abc)" in md


def test_layout_table_is_flattened():
    html = "<table><tr><td><p><strong>IMPORTANT</strong></p><p>Back up first.</p></td></tr></table>"
    md = html_to_markdown(html)
    assert "|" not in md
    assert "**IMPORTANT**" in md and "Back up first." in md


def test_data_table_gets_header_row():
    html = (
        "<table><tr><td><strong>Device</strong></td><td><strong>Path</strong></td></tr>"
        "<tr><td>USB 1</td><td>/home/sdb1</td></tr></table>"
    )
    md = html_to_markdown(html)
    assert "| **Device** | **Path** |\n| --- | --- |\n| USB 1 | /home/sdb1 |" in md


def test_adjacent_bold_runs_are_merged():
    assert "**Pro Plus plan**" in html_to_markdown("<p><strong>Pro Plus</strong><strong>plan</strong></p>")


def test_document_starts_with_title_and_article_url():
    md = build_article_markdown("Add a Video", "https://support.optisigns.com/hc/en-us/articles/1-Add", "<p>Hi</p>")
    assert md.startswith("# Add a Video\n\nArticle URL: https://support.optisigns.com/hc/en-us/articles/1-Add\n")


def test_heading_slug_matches_github_style():
    assert heading_slug("How Do I Add a YouTube Video?") == "how-do-i-add-a-youtube-video"


def test_image_without_alt_is_kept():
    assert "See ![](a.png) here" in html_to_markdown('<p>See <img src="a.png"> here</p>')


def test_anchor_marker_wrapping_heading_keeps_text():
    assert "## Setup Guide" in html_to_markdown('<h2><a name="setup">Setup Guide</a></h2>')


def test_data_table_nested_in_layout_table_survives():
    html = (
        '<table><tr><td><img src="x.png" alt="x">'
        "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table></td></tr></table>"
    )
    assert "| A | B |\n| --- | --- |\n| 1 | 2 |" in html_to_markdown(html)
