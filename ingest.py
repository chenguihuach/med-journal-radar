from __future__ import annotations

import argparse

from src.crossref_fetcher import enrich_by_title as crossref_by_title
from src.db import get_session, init_db
from src.dedupe import upsert_article
from src.models import FetchLog
from src.pubmed_fetcher import enrich_by_title as pubmed_by_title
from src.pubmed_fetcher import fetch_latest_by_query as pubmed_latest
from src.rss_fetcher import fetch_journal_entries
from src.translator import translate_article
from src.utils import ROOT, load_yaml


def ingest(
    auto_translate: bool = False,
    enrich_metadata: bool = False,
    selected_feeds: dict[str, list[str]] | None = None,
) -> dict:
    init_db()
    config = load_yaml(ROOT / "config" / "journals.yaml")
    totals = {"fetched": 0, "inserted": 0, "updated": 0, "feeds": []}
    with get_session() as session:
        for journal in config.get("journals", []):
            errors: list[str] = []
            try:
                selected = (selected_feeds or {}).get(journal.get("name", ""))
                if journal.get("pubmed_query") and not journal.get("feed_urls") and not selected:
                    rows = pubmed_latest(journal["pubmed_query"], journal.get("name", ""), retmax=30)
                    feeds = []
                else:
                    rows, feeds = fetch_journal_entries(journal, selected)
                if not rows and journal.get("pubmed_query"):
                    rows = pubmed_latest(journal["pubmed_query"], journal.get("name", ""), retmax=30)
                totals["feeds"].extend([f"{journal.get('name')}: {f.url} ({f.entries_count})" for f in feeds])
                fetched = inserted = updated = 0
                seen_keys: set[tuple[str, str]] = set()
                for row in rows:
                    fetched += 1
                    key = (
                        row.get("doi")
                        or row.get("url")
                        or f"{row.get('journal', '')}:{row.get('title_en', '')}"
                    )
                    feed_key = (row.get("journal", ""), key)
                    if feed_key in seen_keys:
                        continue
                    seen_keys.add(feed_key)
                    try:
                        if enrich_metadata and not row.get("doi"):
                            row.update({k: v for k, v in crossref_by_title(row["title_en"], row.get("journal")).items() if v and not row.get(k)})
                        if enrich_metadata and (not row.get("abstract_en") or not row.get("pmid")):
                            row.update({k: v for k, v in pubmed_by_title(row["title_en"]).items() if v and not row.get(k)})
                        article, is_new, is_updated = upsert_article(session, row)
                        inserted += int(is_new)
                        updated += int(is_updated)
                        if is_new and auto_translate:
                            translate_article(session, article)
                        else:
                            session.commit()
                    except Exception as exc:
                        session.rollback()
                        title = (row.get("title_en") or "untitled")[:120]
                        errors.append(f"{title}: {exc}")
                status = "success" if not errors else "partial_success"
                feed_message = "; ".join(totals["feeds"][-10:])
                error_message = " | errors: " + " || ".join(errors[:5]) if errors else ""
                session.add(FetchLog(source=journal.get("name"), status=status, fetched_count=fetched, inserted_count=inserted, updated_count=updated, message=feed_message + error_message))
                session.commit()
                totals["fetched"] += fetched
                totals["inserted"] += inserted
                totals["updated"] += updated
            except Exception as exc:
                session.rollback()
                session.add(FetchLog(source=journal.get("name"), status="failed", message=str(exc)))
                session.commit()
    return totals


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--translate", action="store_true", help="Auto-translate newly inserted articles.")
    parser.add_argument("--enrich-metadata", action="store_true", help="Use Crossref/PubMed to fill missing metadata. Slower.")
    args = parser.parse_args()
    result = ingest(auto_translate=args.translate, enrich_metadata=args.enrich_metadata)
    print(result)
