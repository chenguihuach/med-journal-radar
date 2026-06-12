from __future__ import annotations

import os
from urllib.parse import urlencode

import requests

from .utils import clean_text, headers, load_env, normalize_doi, parse_date


def enrich_by_title(title: str, journal: str | None = None) -> dict:
    load_env()
    params = {"query.title": title, "rows": 1}
    if journal:
        params["query.container-title"] = journal
    mailto = os.getenv("CROSSREF_MAILTO")
    if mailto:
        params["mailto"] = mailto
    url = "https://api.crossref.org/works?" + urlencode(params)
    try:
        resp = requests.get(url, headers=headers(), timeout=15)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
    except Exception:
        return {}
    if not items:
        return {}
    item = items[0]
    date_parts = (item.get("published-print") or item.get("published-online") or item.get("created") or {}).get("date-parts", [])
    publication_date = None
    if date_parts and date_parts[0]:
        parts = date_parts[0] + [1, 1]
        publication_date = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    return {
        "doi": normalize_doi(item.get("DOI")),
        "publication_date": publication_date,
        "authors": _authors(item.get("author")),
        "article_type": item.get("type"),
        "url": item.get("URL"),
    }


def enrich_by_doi(doi: str) -> dict:
    load_env()
    params = {}
    mailto = os.getenv("CROSSREF_MAILTO")
    if mailto:
        params["mailto"] = mailto
    suffix = "?" + urlencode(params) if params else ""
    try:
        resp = requests.get(f"https://api.crossref.org/works/{doi}{suffix}", headers=headers(), timeout=15)
        resp.raise_for_status()
        item = resp.json().get("message", {})
    except Exception:
        return {}
    return {
        "doi": normalize_doi(item.get("DOI")),
        "publication_date": parse_date(item.get("published", {}).get("date-parts", [[None]])[0]),
        "authors": _authors(item.get("author")),
        "article_type": clean_text(item.get("type")),
        "url": item.get("URL"),
    }


def _authors(authors: list[dict] | None) -> str | None:
    if not authors:
        return None
    names = []
    for a in authors[:20]:
        name = " ".join(x for x in [a.get("given"), a.get("family")] if x)
        if name:
            names.append(name)
    return "; ".join(names) or None
