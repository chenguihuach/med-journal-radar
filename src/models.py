from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .utils import utcnow


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doi: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    pmid: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_en: Mapped[str] = mapped_column(Text, nullable=False)
    title_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal: Mapped[str] = mapped_column(Text, nullable=False)
    publication_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="rss")
    article_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_status: Mapped[str] = mapped_column(Text, nullable=False, default="not_translated")
    ai_interpretation_status: Mapped[str] = mapped_column(Text, nullable=False, default="not_requested")
    is_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_starred: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    interpretations: Mapped[list["ArticleInterpretation"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", order_by="desc(ArticleInterpretation.created_at)"
    )

    __table_args__ = (UniqueConstraint("title_en", "journal", name="uq_article_title_journal"),)


class ArticleInterpretation(Base):
    __tablename__ = "article_interpretations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=False, index=True)
    topic_type: Mapped[str | None] = mapped_column(Text)
    article_category: Mapped[str | None] = mapped_column(Text)
    study_design: Mapped[str | None] = mapped_column(Text)
    population: Mapped[str | None] = mapped_column(Text)
    sample_size: Mapped[str | None] = mapped_column(Text)
    data_source: Mapped[str | None] = mapped_column(Text)
    ai_or_statistical_method: Mapped[str | None] = mapped_column(Text)
    comparator: Mapped[str | None] = mapped_column(Text)
    primary_outcome: Mapped[str | None] = mapped_column(Text)
    main_results: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    clinical_relevance: Mapped[str | None] = mapped_column(Text)
    limitations_from_abstract: Mapped[str | None] = mapped_column(Text)
    evidence_snippets: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    article: Mapped[Article] = relationship(back_populates="interpretations")


class FetchLog(Base):
    __tablename__ = "fetch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)


class DailyActivity(Base):
    __tablename__ = "daily_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_date: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    starred_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
