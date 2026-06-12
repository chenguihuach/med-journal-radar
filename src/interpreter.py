from __future__ import annotations

from sqlalchemy.orm import Session

from .llm_client import DeepSeekClient, JSONParseError
from .models import Article, ArticleInterpretation
from .utils import ROOT, as_json_text, has_deepseek_api_key, load_yaml, utcnow


FIELDS = [
    "topic_type",
    "article_category",
    "study_design",
    "population",
    "sample_size",
    "data_source",
    "ai_or_statistical_method",
    "comparator",
    "primary_outcome",
    "main_results",
    "conclusion",
    "clinical_relevance",
    "limitations_from_abstract",
    "evidence_snippets",
    "confidence",
]


def interpret_article(session: Session, article: Article, replace_existing: bool = True) -> bool:
    if not has_deepseek_api_key():
        article.ai_interpretation_status = "failed"
        article.updated_at = utcnow()
        session.commit()
        return False
    prompt_tpl = load_yaml(ROOT / "config" / "prompts.yaml")["interpretation"]
    prompt = (
        prompt_tpl.replace("{journal}", article.journal or "")
        .replace("{publication_date}", article.publication_date or "")
        .replace("{article_type}", article.article_type or "")
        .replace("{title_en}", article.title_en or "")
        .replace("{abstract_en}", article.abstract_en or "")
    )
    article.ai_interpretation_status = "processing"
    session.commit()
    try:
        client = DeepSeekClient()
        data, raw = client.json_chat(prompt)
        interp = article.interpretations[0] if replace_existing and article.interpretations else ArticleInterpretation(article_id=article.id)
        for field in FIELDS:
            value = data.get(field)
            if isinstance(value, (dict, list)):
                value = as_json_text(value)
            setattr(interp, field, value)
        interp.model_name = client.model
        interp.raw_json = raw
        interp.updated_at = utcnow()
        session.add(interp)
        article.ai_interpretation_status = "completed"
        article.updated_at = utcnow()
        session.commit()
        return True
    except JSONParseError as exc:
        interp = ArticleInterpretation(article_id=article.id)
        interp.raw_json = exc.raw_response
        interp.model_name = getattr(locals().get("client", None), "model", None)
        interp.updated_at = utcnow()
        session.add(interp)
        article.ai_interpretation_status = "failed"
        article.updated_at = utcnow()
        session.commit()
        return False
    except Exception:
        article.ai_interpretation_status = "failed"
        article.updated_at = utcnow()
        session.commit()
        return False
