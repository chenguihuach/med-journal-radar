from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from .utils import clean_text, headers, normalize_doi, parse_date


@dataclass
class FeedCandidate:
    url: str
    label: str
    entries_count: int


def discover_feeds(journal: dict) -> list[FeedCandidate]:
    seeds = [u for u in journal.get("feed_urls", []) if u]
    for page in [journal.get("homepage_url"), journal.get("rss_page_url")]:
        if page:
            seeds.extend(_discover_from_page(page))
    candidates: dict[str, FeedCandidate] = {}
    for url in dict.fromkeys(seeds):
        parsed = feedparser.parse(url, request_headers=headers())
        count = len(parsed.entries)
        if count > 0:
            candidates[url] = FeedCandidate(url=url, label=_feed_label(url, parsed), entries_count=count)
    return sorted(candidates.values(), key=lambda c: _priority(journal.get("name", ""), c.url, c.label))


def _discover_from_page(url: str) -> list[str]:
    try:
        resp = requests.get(url, headers=headers(), timeout=15)
        resp.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    found: list[str] = []
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel", [])).lower()
        typ = (link.get("type") or "").lower()
        if "alternate" in rel and ("rss" in typ or "atom" in typ):
            href = link.get("href")
            if href:
                found.append(urljoin(resp.url, href))
    wanted = re.compile(r"(rss|rss feed|online first|current issue|advance online publication)", re.I)
    for a in soup.find_all("a"):
        text = clean_text(a.get_text(" ")) or ""
        href = a.get("href")
        if href and wanted.search(text):
            found.append(urljoin(resp.url, href))
    return found


def _feed_label(url: str, parsed) -> str:
    title = clean_text(parsed.feed.get("title")) if getattr(parsed, "feed", None) else None
    return title or url


def _priority(journal: str, url: str, label: str) -> tuple[int, str]:
    text = f"{url} {label}".lower()
    journal_l = journal.lower()
    score = 50
    if "jama" in journal_l and ("onlinefirst" in text or "online first" in text):
        score -= 30
    if "lancet" in journal_l and ("onlinefirst" in text or "online first" in text):
        score -= 30
    if "nature medicine" in journal_l and ("vaop" in text or "advance online publication" in text):
        score -= 30
    if "current" in text or "current issue" in text:
        score -= 10
    return score, text


def fetch_journal_entries(journal: dict, selected_urls: list[str] | None = None) -> tuple[list[dict], list[FeedCandidate]]:
    configured_urls = [u for u in journal.get("feed_urls", []) if u]
    if selected_urls:
        feeds = [FeedCandidate(url=u, label=u, entries_count=0) for u in selected_urls]
        urls = selected_urls
    elif configured_urls:
        feeds = [FeedCandidate(url=u, label=u, entries_count=0) for u in configured_urls]
        urls = configured_urls
    else:
        feeds = discover_feeds(journal)
        urls = [f.url for f in feeds]
    articles: list[dict] = []
    for feed_url in urls:
        try:
            parsed = feedparser.parse(feed_url, request_headers=headers())
        except Exception:
            continue
        if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", []):
            continue
        for feed in feeds:
            if feed.url == feed_url:
                feed.entries_count = len(parsed.entries)
        for entry in parsed.entries:
            articles.append(parse_entry(entry, journal.get("name", ""), feed_url))
    return articles, feeds


def parse_entry(entry, journal_name: str, feed_url: str) -> dict:
    title = clean_text(entry.get("title")) or "Untitled"
    summary = clean_text(entry.get("summary") or entry.get("description"))
    url = entry.get("link")
    doi = _entry_doi(entry, title, summary, url)
    authors = _entry_authors(entry)
    tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
    article_type = tags[0] if tags else None
    return {
        "doi": doi,
        "pmid": _entry_pmid(entry),
        "title_en": title,
        "abstract_en": summary,
        "journal": journal_name,
        "publication_date": parse_date(entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("published") or entry.get("updated")),
        "authors": authors,
        "url": url,
        "source": f"rss:{feed_url}",
        "article_type": article_type,
    }


def _entry_doi(entry, *texts: str | None) -> str | None:
    for key in ("doi", "dc_identifier", "prism_doi"):
        doi = normalize_doi(entry.get(key))
        if doi:
            return doi
    for link in entry.get("links", []):
        doi = normalize_doi(link.get("href"))
        if doi:
            return doi
    for text in texts:
        doi = normalize_doi(text)
        if doi:
            return doi
    return None


def _entry_pmid(entry) -> str | None:
    text = " ".join(str(entry.get(k, "")) for k in ("id", "guid", "link"))
    m = re.search(r"(?:pmid[:/_-]?|pubmed/)(\d+)", text, re.I)
    return m.group(1) if m else None


def _entry_authors(entry) -> str | None:
    if entry.get("authors"):
        names = [a.get("name") for a in entry.authors if a.get("name")]
        return "; ".join(names) or None
    return clean_text(entry.get("author"))
