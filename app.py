from __future__ import annotations

from datetime import date, timedelta

import streamlit as st
from sqlalchemy import func, or_, select

from ingest import ingest
from src.activity import load_activity_days, record_today_visit, refresh_today_starred_count
from src.article_filters import focus_relevance_clause, medical_relevance_clause
from src.db import get_session, init_db
from src.interpreter import interpret_article
from src.models import Article, ArticleInterpretation
from src.rss_fetcher import discover_feeds
from src.translator import translate_article, translation_provider
from src.utils import ROOT, env_file_exists, has_deepseek_api_key, load_yaml, utcnow
from translate_missing import translate_missing

st.set_page_config(page_title="Med Journal Radar", layout="wide")


def init() -> None:
    init_db()
    if not st.session_state.get("activity_recorded"):
        with get_session() as session:
            record_today_visit(session)
        st.session_state["activity_recorded"] = True


def render_config_status() -> None:
    if not env_file_exists():
        st.info("No .env file found. Copy .env.example to .env to enable DeepSeek translation and AI interpretation.")
    elif not has_deepseek_api_key():
        st.warning("DEEPSEEK_API_KEY is empty. Article fetching works, but translation and AI interpretation are disabled.")


def stats() -> dict[str, int]:
    today = date.today().isoformat()
    with get_session() as session:
        return {
            "Articles": session.scalar(select(func.count(Article.id))) or 0,
            "Added today": session.scalar(select(func.count(Article.id)).where(func.date(Article.created_at) == today)) or 0,
            "Translated": session.scalar(select(func.count(Article.id)).where(Article.translation_status == "translated")) or 0,
            "AI interpreted": session.scalar(select(func.count(Article.id)).where(Article.ai_interpretation_status == "completed")) or 0,
            "Starred": session.scalar(select(func.count(Article.id)).where(Article.is_starred == 1)) or 0,
            "Unread": session.scalar(select(func.count(Article.id)).where(Article.is_read == 0)) or 0,
        }


def load_articles(filters: dict) -> list[Article]:
    with get_session() as session:
        stmt = select(Article).order_by(Article.publication_date.desc(), Article.created_at.desc())
        if filters["scope"] == "Medical relevance":
            stmt = stmt.where(medical_relevance_clause())
        elif filters["scope"] == "Medical AI / cardiovascular":
            stmt = stmt.where(focus_relevance_clause())
        if filters["journals"]:
            stmt = stmt.where(Article.journal.in_(filters["journals"]))
        if filters["read"] != "All":
            stmt = stmt.where(Article.is_read == (1 if filters["read"] == "Read" else 0))
        if filters["starred"] != "All":
            stmt = stmt.where(Article.is_starred == (1 if filters["starred"] == "Starred" else 0))
        if filters["translated"] != "All":
            if filters["translated"] == "Translated":
                stmt = stmt.where(Article.translation_status == "translated")
            else:
                stmt = stmt.where(Article.translation_status.in_(["not_translated", "failed"]))
        if filters["interpreted"] != "All":
            if filters["interpreted"] == "Interpreted":
                stmt = stmt.where(Article.ai_interpretation_status == "completed")
            else:
                stmt = stmt.where(Article.ai_interpretation_status.in_(["not_requested", "failed"]))
        if filters["article_types"]:
            stmt = stmt.where(Article.article_type.in_(filters["article_types"]))
        if filters["date_range"]:
            start, end = filters["date_range"]
            stmt = stmt.where(Article.publication_date >= start.isoformat(), Article.publication_date <= end.isoformat())
        query = (filters["query"] or "").strip()
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Article.title_en.ilike(like),
                    Article.title_zh.ilike(like),
                    Article.abstract_en.ilike(like),
                    Article.abstract_zh.ilike(like),
                    Article.notes.ilike(like),
                )
            )
        return list(session.execute(stmt.limit(200)).scalars())


def options() -> tuple[list[str], list[str]]:
    with get_session() as session:
        journals = [x for x in session.execute(select(Article.journal).distinct().order_by(Article.journal)).scalars() if x]
        types = [x for x in session.execute(select(Article.article_type).distinct().order_by(Article.article_type)).scalars() if x]
    return journals, types


def update_article(article_id: int, **values) -> None:
    with get_session() as session:
        article = session.get(Article, article_id)
        if article:
            for key, value in values.items():
                setattr(article, key, value)
            article.updated_at = utcnow()
            session.commit()
            if "is_starred" in values:
                refresh_today_starred_count(session)


def render_activity_heatmap(days: int = 30) -> None:
    today = date.today()
    start = today - timedelta(days=days - 1)
    with get_session() as session:
        activities = load_activity_days(session, days)
    max_starred = max([a.starred_count for a in activities.values()] + [1])
    st.caption("Recent reading activity")
    cols = st.columns(10)
    for index, day_offset in enumerate(range(days - 1, -1, -1)):
        current = today - timedelta(days=day_offset)
        activity = activities.get(current.isoformat())
        starred = activity.starred_count if activity else 0
        color = activity_color(starred, max_starred) if activity else "#e5e7eb"
        cols[index % 10].markdown(
            f"<div title='{current.isoformat()}: {starred} starred' style='height:14px; background:{color}; border-radius:3px; margin:2px 0;'></div>",
            unsafe_allow_html=True,
        )


def activity_color(starred_count: int, max_starred: int) -> str:
    if starred_count <= 0:
        return "#bbf7d0"
    ratio = starred_count / max(max_starred, 1)
    if ratio >= 0.75:
        return "#166534"
    if ratio >= 0.45:
        return "#22c55e"
    return "#86efac"


def latest_interpretation(article_id: int) -> ArticleInterpretation | None:
    with get_session() as session:
        return session.execute(
            select(ArticleInterpretation)
            .where(ArticleInterpretation.article_id == article_id)
            .order_by(ArticleInterpretation.created_at.desc())
        ).scalar_one_or_none()


def render_interpretation(interp: ArticleInterpretation | None) -> None:
    if not interp:
        st.info("No AI interpretation saved yet.")
        return
    st.warning("AI interpretation is based only on title, abstract, and metadata. It is not a full-text review.")
    labels = [
        ("Study design", interp.study_design),
        ("Population", interp.population),
        ("Sample size", interp.sample_size),
        ("Data source", interp.data_source),
        ("AI/statistical method", interp.ai_or_statistical_method),
        ("Comparator", interp.comparator),
        ("Primary outcome", interp.primary_outcome),
        ("Main results", interp.main_results),
        ("Conclusion", interp.conclusion),
        ("Clinical relevance", interp.clinical_relevance),
        ("Limitations visible from abstract", interp.limitations_from_abstract),
        ("Evidence snippets", interp.evidence_snippets),
        ("Confidence", interp.confidence),
    ]
    for label, value in labels:
        st.markdown(f"**{label}:** {value or 'Not reported in the abstract'}")
    if interp.raw_json and not any(value for _, value in labels):
        with st.expander("Raw model response"):
            st.code(interp.raw_json)


def run_interpret(article_id: int) -> None:
    if not has_deepseek_api_key():
        st.warning("DeepSeek API key is required for AI interpretation. Copy .env.example to .env and set DEEPSEEK_API_KEY.")
        return
    with get_session() as session:
        article = session.get(Article, article_id)
        ok = interpret_article(session, article) if article else False
    st.toast("AI interpretation saved." if ok else "AI interpretation failed. Check DeepSeek configuration or retry later.")
    st.rerun()


def render_article(article: Article) -> None:
    with st.container(border=True):
        st.markdown(f"**{article.journal}** - {article.publication_date or 'date unknown'} - {article.article_type or 'type unknown'}")
        st.markdown(f"### {article.title_en}")
        if article.title_zh:
            st.markdown(f"**{article.title_zh}**")
        st.write((article.abstract_zh or article.abstract_en or "No abstract available.")[:700])
        st.caption(
            f"DOI: {article.doi or '-'} | PMID: {article.pmid or '-'} | "
            f"translation: {article.translation_status} | AI: {article.ai_interpretation_status}"
        )
        if article.url:
            st.link_button("Open article page", article.url)

        c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.4])
        if article.ai_interpretation_status == "completed":
            if c1.button("View AI", key=f"view-ai-{article.id}"):
                st.session_state[f"show-ai-{article.id}"] = True
            if c2.button("Re-interpret", key=f"redo-ai-{article.id}"):
                run_interpret(article.id)
        elif article.ai_interpretation_status == "failed":
            if c1.button("Retry AI", key=f"retry-ai-{article.id}"):
                run_interpret(article.id)
        else:
            if c1.button("AI interpret", key=f"ai-{article.id}"):
                run_interpret(article.id)

        if c3.button("Unstar" if article.is_starred else "Star", key=f"star-{article.id}"):
            update_article(article.id, is_starred=0 if article.is_starred else 1)
            st.rerun()
        if c4.button("Mark unread" if article.is_read else "Mark read", key=f"read-{article.id}"):
            update_article(article.id, is_read=0 if article.is_read else 1)
            st.rerun()
        if c5.button("Translate Chinese info", key=f"tr-{article.id}"):
            if not has_deepseek_api_key() and translation_provider() == "deepseek":
                st.warning("DeepSeek API key is required for translation. Copy .env.example to .env and set DEEPSEEK_API_KEY.")
            else:
                with get_session() as session:
                    fresh = session.get(Article, article.id)
                    ok = translate_article(session, fresh) if fresh else False
                st.toast("Translation saved." if ok else "Translation failed. Check API configuration or retry later.")
                st.rerun()

        with st.expander("Details"):
            st.markdown("**English abstract**")
            st.write(article.abstract_en or "No English abstract in RSS/metadata.")
            st.markdown("**Chinese abstract**")
            st.write(article.abstract_zh or "Not translated yet.")
            st.markdown(f"**Authors:** {article.authors or '-'}")
            st.markdown(f"**Source:** {article.source}")
            notes = st.text_area("Notes", article.notes or "", key=f"notes-{article.id}")
            if st.button("Save notes", key=f"save-notes-{article.id}"):
                update_article(article.id, notes=notes)
                st.toast("Notes saved.")
            if article.ai_interpretation_status == "completed" or st.session_state.get(f"show-ai-{article.id}"):
                render_interpretation(latest_interpretation(article.id))


def feed_selector() -> dict[str, list[str]]:
    config = load_yaml(ROOT / "config" / "journals.yaml")
    selected: dict[str, list[str]] = {}
    with st.expander("RSS feed discovery and selection"):
        st.caption("Feed discovery tests configured URLs, homepages, and RSS pages when available.")
        for journal in config.get("journals", []):
            name = journal.get("name", "")
            if st.button(f"Discover feeds for {name}", key=f"discover-{name}"):
                st.session_state[f"feeds-{name}"] = discover_feeds(journal)
            feeds = st.session_state.get(f"feeds-{name}", [])
            if feeds:
                choices = [f.url for f in feeds]
                labels = {f.url: f"{f.label} ({f.entries_count}) - {f.url}" for f in feeds}
                selected[name] = st.multiselect(name, choices, default=choices[:2], format_func=lambda url: labels[url], key=f"select-{name}")
    return selected


def sidebar_filters(journals: list[str], article_types: list[str]) -> dict:
    with st.sidebar:
        st.header("Filters")
        date_preset = st.selectbox("Date range", ["Past 3 days", "Past 7 days", "Past 30 days", "All dates", "Custom"])
        custom_date_range = None
        if date_preset == "Custom":
            d1, d2 = st.columns(2)
            start_date = d1.date_input("Start", value=date.today() - timedelta(days=7))
            end_date = d2.date_input("End", value=date.today())
            custom_date_range = (start_date, end_date)
        date_ranges = {
            "Past 3 days": (date.today() - timedelta(days=2), date.today()),
            "Past 7 days": (date.today() - timedelta(days=6), date.today()),
            "Past 30 days": (date.today() - timedelta(days=29), date.today()),
            "All dates": None,
            "Custom": custom_date_range,
        }
        return {
            "scope": st.selectbox("Scope", ["Medical relevance", "Medical AI / cardiovascular", "All articles"]),
            "journals": st.multiselect("Journals", journals),
            "date_range": date_ranges[date_preset],
            "read": st.selectbox("Read status", ["All", "Unread", "Read"]),
            "starred": st.selectbox("Starred status", ["All", "Starred", "Not starred"]),
            "translated": st.selectbox("Translation status", ["All", "Translated", "Not translated"]),
            "interpreted": st.selectbox("AI status", ["All", "Interpreted", "Not interpreted"]),
            "article_types": st.multiselect("Article types", article_types),
            "query": st.text_input("Search title, abstract, or notes"),
        }


def main() -> None:
    init()
    st.title("Med Journal Radar")
    st.caption("Local medical journal tracker with bilingual metadata and on-demand AI interpretation.")
    render_config_status()

    cols = st.columns(6)
    for col, (label, value) in zip(cols, stats().items()):
        col.metric(label, value)
    render_activity_heatmap()

    selected_feeds = feed_selector()
    a, b, c = st.columns([1, 1.3, 1])
    if a.button("Fetch latest", type="primary"):
        with st.spinner("Fetching RSS/PubMed metadata and upserting articles..."):
            result = ingest(auto_translate=False, enrich_metadata=False, selected_feeds=selected_feeds)
        st.success(f"Fetched {result['fetched']} articles, inserted {result['inserted']}, updated {result['updated']}.")
        if result.get("feeds"):
            with st.expander("Feeds used"):
                st.write("\n".join(result["feeds"]))

    translate_limit = b.number_input("Max translations", min_value=1, max_value=200, value=30, step=10)
    b.caption(f"Translation provider: {translation_provider()}")
    if b.button("Translate missing Chinese info"):
        if not has_deepseek_api_key() and translation_provider() == "deepseek":
            st.warning("DeepSeek API key is required for translation. Copy .env.example to .env and set DEEPSEEK_API_KEY.")
        else:
            total, ok = translate_missing(limit=int(translate_limit))
            st.success(f"Translation complete: {ok}/{total}")
    if c.button("Refresh page"):
        st.rerun()

    journals, article_types = options()
    filters = sidebar_filters(journals, article_types)
    articles = load_articles(filters)
    st.subheader(f"Articles ({len(articles)})")
    if not articles:
        st.info("No articles yet. Click Fetch latest or run python ingest.py.")
    for article in articles:
        render_article(article)


if __name__ == "__main__":
    main()
