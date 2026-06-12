from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Article
from .utils import clean_text, normalize_doi, utcnow

UPDATABLE_FIELDS = ("doi", "pmid", "abstract_en", "publication_date", "authors", "article_type", "url")


def find_existing(session: Session, data: dict) -> Article | None:
    doi = normalize_doi(data.get("doi"))
    url = data.get("url")
    title = clean_text(data.get("title_en"))
    journal = data.get("journal")
    if doi:
        found = session.execute(select(Article).where(Article.doi == doi)).scalar_one_or_none()
        if found:
            return found
    if url:
        found = session.execute(select(Article).where(Article.url == url)).scalar_one_or_none()
        if found:
            return found
    if title and journal:
        return session.execute(
            select(Article).where(Article.title_en == title, Article.journal == journal)
        ).scalar_one_or_none()
    return None


def upsert_article(session: Session, data: dict) -> tuple[Article, bool, bool]:
    data = dict(data)
    data["doi"] = normalize_doi(data.get("doi"))
    data["title_en"] = clean_text(data.get("title_en")) or "Untitled"
    data["abstract_en"] = clean_text(data.get("abstract_en"))
    existing = find_existing(session, data)
    if not existing:
        article = Article(**{k: v for k, v in data.items() if hasattr(Article, k)})
        session.add(article)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            existing = find_existing(session, data)
            if existing:
                return _update_missing_fields(session, existing, data)
            raise
        return article, True, False

    return _update_missing_fields(session, existing, data)


def _update_missing_fields(session: Session, existing: Article, data: dict) -> tuple[Article, bool, bool]:
    changed = False
    for field in UPDATABLE_FIELDS:
        current = getattr(existing, field)
        incoming = data.get(field)
        if field == "doi" and incoming:
            doi_owner = session.execute(select(Article).where(Article.doi == incoming)).scalar_one_or_none()
            if doi_owner and doi_owner.id != existing.id:
                continue
        if (not current) and incoming:
            setattr(existing, field, incoming)
            changed = True
    if changed:
        existing.updated_at = utcnow()
        session.flush()
    return existing, False, changed
