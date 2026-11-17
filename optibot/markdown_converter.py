"""Turns Zendesk article HTML into clean Markdown for embedding."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

DROP_TAGS = ["script", "style", "noscript", "form", "button", "input", "colgroup", "col", "nav", "aside"]
KEEP_ATTRS = {"a": {"href"}, "img": {"src", "alt"}, "ol": {"start"}}
HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
BLOCK_TAGS = ["p", "ul", "ol", "img", "pre", "table", "blockquote", *HEADINGS]
LAYOUT_ONLY_TAGS = ["ul", "ol", "img", "pre", "table", "blockquote", "iframe", "video", *HEADINGS]
KNOWN_TAGS = {
    "a", "img", "p", "br", "hr", "div", "ul", "ol", "li", "pre", "code", "blockquote",
    "strong", "b", "em", "i", "table", "thead", "tbody", "tr", "th", "td", "sup", "sub", *HEADINGS,
}


def heading_slug(text: str) -> str:
    """GitHub-style anchor slug, so in-page links keep working in Markdown viewers."""
    slug = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return re.sub(r"\s", "-", slug)


def _replace_embeds(soup: BeautifulSoup) -> None:
    # Video players cannot be embedded in Markdown; keep a link to the media instead.
    for tag in soup.find_all(["iframe", "video"]):
        src = tag.get("src") or (tag.find("source") or {}).get("src", "")
        if not src:
            tag.decompose()
            continue
        if src.startswith("//"):
            src = "https:" + src
        link = soup.new_tag("a", href=src)
        link.string = "Embedded video"
        para = soup.new_tag("p")
        para.append(link)
        tag.replace_with(para)
    for img in soup.find_all("img"):
        if img.get("src", "").startswith("data:"):  # inline base64 blobs are noise for retrieval
            img.decompose()


def _rewrite_anchor_links(soup: BeautifulSoup) -> None:
    targets = {}
    for el in soup.find_all(id=True):
        heading = el if el.name in HEADINGS else el.find_parent(HEADINGS)
        if heading is not None:
            targets[el["id"]] = heading_slug(heading.get_text(" ", strip=True))
    # Zendesk TOCs point at `<a name="X"></a>` markers placed just before the heading.
    for marker in soup.find_all("a", attrs={"name": True}, href=False):
        heading = marker.find_parent(HEADINGS) or marker.find_next(HEADINGS)
        if heading is not None:
            targets.setdefault(marker["name"], heading_slug(heading.get_text(" ", strip=True)))
        marker.unwrap()  # the marker may wrap the heading text itself
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("#") and href[1:] in targets:
            link["href"] = "#" + targets[href[1:]]


def _is_data_table(table: Tag) -> bool:
    """Data tables become Markdown tables; layout tables (callouts, image grids) are flattened."""
    rows = table.find_all("tr")
    if len(rows) < 2 or max(len(r.find_all(["td", "th"])) for r in rows) < 2:
        return False
    return table.find(LAYOUT_ONLY_TAGS) is None


def _promote_header_row(table: Tag) -> None:
    """Zendesk editors write the header as a plain first row; without <th> Markdown gets an empty header."""
    if table.find("th") is None:
        for cell in table.find("tr").find_all("td"):
            cell.name = "th"


def _flatten_tables(soup: BeautifulSoup) -> None:
    # Innermost tables first so nested layout tables unwrap cleanly.
    for table in reversed(soup.find_all("table")):
        if _is_data_table(table):
            _promote_header_row(table)
            for p in table.find_all("p"):  # Markdown cells are single-line
                if p.find_next_sibling("p"):
                    p.append(soup.new_tag("br"))
                p.unwrap()
            continue
        # Only this table's own structure: a nested data table must stay intact.
        own = [t for t in table.find_all(["td", "th", "tr", "tbody", "thead", "tfoot"])
               if t.find_parent("table") is table]
        for tag in own:
            if tag.name in ("td", "th"):
                tag.name = "div" if tag.find(BLOCK_TAGS) else "p"
            else:
                tag.unwrap()
        table.name = "div"


def _clean_tree(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(DROP_TAGS):
        tag.decompose()
    _replace_embeds(soup)
    _rewrite_anchor_links(soup)
    _flatten_tables(soup)
    # Prism/Wix wrappers and styling tags carry no meaning in Markdown.
    for tag in soup.find_all(["span", "font", "u", "figure", "figcaption", "article", "section"]):
        tag.unwrap()
    for tag in soup.find_all(["strong", "b", "em", "i"]):
        if not tag.get_text(strip=True) and tag.find("img") is None:
            tag.unwrap()
    for tag in soup.find_all(HEADINGS):  # editors leave `<h3>&nbsp;</h3>` spacers
        if not tag.get_text(strip=True).replace("\xa0", ""):
            if tag.find("img") is None:
                tag.decompose()
            else:
                tag.name = "p"  # markdownify drops images inside headings
    for tag in soup.find_all(True):
        if tag.name not in KNOWN_TAGS:  # stray pseudo-tags such as `<your>` from bad copy-paste
            tag.unwrap()
            continue
        allowed = KEEP_ATTRS.get(tag.name, set())
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed}


def _tidy(markdown: str) -> str:
    text = markdown.replace("\xa0", " ").replace("​", "")
    text = re.sub(r"(\w)\*\*\*\*(\w)", r"\1 \2", text)  # adjacent bold runs: **Pro Plus****plan**
    text = re.sub(r"(?<!!)\[\s*\]\([^)]*\)", "", text)  # links with no visible text (not images)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(\n---\n\s*){2,}", "\n---\n\n", text)  # repeated separators
    return text.strip()


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    _clean_tree(soup)
    markdown = markdownify(
        str(soup), heading_style="ATX", bullets="-", strong_em_symbol="*", escape_underscores=False
    )
    return _tidy(markdown)


def build_article_markdown(title: str, url: str, body_html: str) -> str:
    """Full document: title + source URL (used by the bot for citations) + body."""
    return f"# {title}\n\nArticle URL: {url}\n\n{html_to_markdown(body_html)}\n"
