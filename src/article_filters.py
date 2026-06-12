from __future__ import annotations

from sqlalchemy import or_

from .models import Article

MEDICAL_JOURNALS = {
    "Nature Medicine",
    "The Lancet",
    "JAMA",
    "NEJM",
    "The Lancet Digital Health",
    "npj Digital Medicine",
}

MEDICAL_KEYWORDS = [
    "medicine",
    "medical",
    "clinical",
    "clinician",
    "patient",
    "patients",
    "disease",
    "diagnosis",
    "diagnostic",
    "therapy",
    "therapeutic",
    "treatment",
    "trial",
    "cohort",
    "hospital",
    "health",
    "healthcare",
    "epidemiology",
    "mortality",
    "morbidity",
    "cancer",
    "tumor",
    "cardiovascular",
    "cardiology",
    "heart",
    "stroke",
    "myocardial",
    "coronary",
    "hypertension",
    "diabetes",
    "kidney",
    "lung",
    "infection",
    "vaccine",
]

FOCUS_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "large language model",
    "llm",
    "ai",
    "algorithm",
    "prediction model",
    "ehr",
    "electronic health record",
    "cardiovascular",
    "cardiology",
    "heart",
    "stroke",
    "myocardial",
    "coronary",
    "atrial fibrillation",
    "heart failure",
    "hypertension",
]


def medical_relevance_clause():
    return or_(Article.journal.in_(MEDICAL_JOURNALS), _keyword_clause(MEDICAL_KEYWORDS))


def focus_relevance_clause():
    return _keyword_clause(FOCUS_KEYWORDS)


def _keyword_clause(keywords: list[str]):
    clauses = []
    for keyword in keywords:
        like = f"%{keyword}%"
        clauses.extend([Article.title_en.ilike(like), Article.abstract_en.ilike(like), Article.title_zh.ilike(like), Article.abstract_zh.ilike(like)])
    return or_(*clauses)
