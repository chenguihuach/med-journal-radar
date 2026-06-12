from __future__ import annotations

import os
import time
from urllib.parse import urlencode

import requests
from Bio import Entrez

from .utils import clean_text, load_env, normalize_doi


def configure_entrez() -> None:
    load_env()
    Entrez.email = os.getenv("CROSSREF_MAILTO") or "user@example.com"
    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        Entrez.api_key = api_key


def ncbi_sleep() -> None:
    load_env()
    time.sleep(0.12 if os.getenv("NCBI_API_KEY") else 0.34)


def enrich_by_title(title: str) -> dict:
    configure_entrez()
    try:
        ncbi_sleep()
        handle = Entrez.esearch(db="pubmed", term=f"{title}[Title]", retmax=1)
        result = Entrez.read(handle)
        ids = result.get("IdList", [])
        if not ids:
            return {}
        return enrich_by_pmid(ids[0])
    except Exception:
        return {}


def fetch_latest_by_query(query: str, journal_name: str, retmax: int = 30) -> list[dict]:
    configure_entrez()
    try:
        ncbi_sleep()
        handle = Entrez.esearch(db="pubmed", term=query, retmax=retmax, sort="pub date")
        result = Entrez.read(handle)
        ids = result.get("IdList", [])
        if not ids:
            return []
        ncbi_sleep()
        handle = Entrez.efetch(db="pubmed", id=",".join(ids), rettype="xml")
        records = Entrez.read(handle)
    except Exception:
        return []
    rows: list[dict] = []
    for record in records.get("PubmedArticle", []):
        row = _article_from_pubmed_record(record, journal_name)
        if row:
            rows.append(row)
    return rows


def enrich_by_pmid(pmid: str) -> dict:
    configure_entrez()
    try:
        ncbi_sleep()
        handle = Entrez.efetch(db="pubmed", id=pmid, rettype="xml")
        records = Entrez.read(handle)
        article = records["PubmedArticle"][0]["MedlineCitation"]["Article"]
    except Exception:
        return {"pmid": pmid}
    doi = None
    for item in article.get("ELocationID", []):
        if getattr(item, "attributes", {}).get("EIdType") == "doi":
            doi = str(item)
    abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
    abstract = " ".join(str(x) for x in abstract_parts) if abstract_parts else None
    journal = article.get("Journal", {})
    pub_date = journal.get("JournalIssue", {}).get("PubDate", {})
    year = pub_date.get("Year")
    month = pub_date.get("Month", "01")
    day = pub_date.get("Day", "01")
    return {
        "pmid": pmid,
        "doi": normalize_doi(doi),
        "abstract_en": clean_text(abstract),
        "publication_date": f"{year}-{_month(month)}-{int(day):02d}" if year else None,
    }


def _article_from_pubmed_record(record: dict, journal_name: str) -> dict | None:
    citation = record.get("MedlineCitation", {})
    pmid = str(citation.get("PMID", ""))
    article = citation.get("Article", {})
    title = clean_text(article.get("ArticleTitle"))
    if not title:
        return None
    abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
    abstract = " ".join(str(x) for x in abstract_parts) if abstract_parts else None
    doi = None
    for item in article.get("ELocationID", []):
        if getattr(item, "attributes", {}).get("EIdType") == "doi":
            doi = str(item)
    pub_date = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
    publication_date = _pubmed_date(pub_date)
    authors = _pubmed_authors(article.get("AuthorList"))
    article_types = article.get("PublicationTypeList", [])
    article_type = "; ".join(str(x) for x in article_types[:3]) if article_types else None
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
    return {
        "doi": normalize_doi(doi),
        "pmid": pmid or None,
        "title_en": title,
        "abstract_en": clean_text(abstract),
        "journal": journal_name,
        "publication_date": publication_date,
        "authors": authors,
        "url": url,
        "source": f"pubmed:{query_label(journal_name)}",
        "article_type": article_type,
    }


def _pubmed_date(pub_date: dict) -> str | None:
    year = pub_date.get("Year")
    if not year:
        return None
    month = _month(pub_date.get("Month", "01"))
    try:
        day = int(pub_date.get("Day", "01"))
    except Exception:
        day = 1
    return f"{year}-{month}-{day:02d}"


def _pubmed_authors(authors) -> str | None:
    if not authors:
        return None
    names = []
    for author in authors[:20]:
        last = author.get("LastName")
        fore = author.get("ForeName") or author.get("Initials")
        name = " ".join(x for x in [fore, last] if x)
        if name:
            names.append(name)
    return "; ".join(names) or None


def query_label(journal_name: str) -> str:
    return journal_name.lower().replace(" ", "_")


def _month(value: str) -> str:
    months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
    try:
        return f"{int(value):02d}"
    except Exception:
        return f"{months.get(value[:3], 1):02d}"
