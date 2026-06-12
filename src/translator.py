from __future__ import annotations

import os

from sqlalchemy.orm import Session

from .llm_client import DeepSeekClient
from .models import Article
from .utils import ROOT, has_deepseek_api_key, load_env, load_yaml, utcnow

MAX_GOOGLE_CHARS = 4500


def translation_provider() -> str:
    load_env()
    return os.getenv("TRANSLATION_PROVIDER", "deepseek").strip().lower()


def translate_article(session: Session, article: Article) -> bool:
    try:
        if translation_provider() == "deepseek":
            if not has_deepseek_api_key():
                raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
            data = translate_with_deepseek(article)
        else:
            data = translate_with_google(article)
        article.title_zh = data.get("title_zh") or article.title_zh
        article.abstract_zh = data.get("abstract_zh") or article.abstract_zh
        article.translation_status = "translated"
        article.updated_at = utcnow()
        session.commit()
        return True
    except Exception:
        article.translation_status = "failed"
        article.updated_at = utcnow()
        session.commit()
        return False


def translate_with_google(article: Article) -> dict[str, str]:
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        raise RuntimeError("deep-translator is not installed. Run: pip install -r requirements.txt") from exc

    translator = GoogleTranslator(source="en", target="zh-CN")
    title_zh = translator.translate(article.title_en) if article.title_en else ""
    abstract_zh = translate_long_text_google(translator, article.abstract_en or "") if article.abstract_en else ""
    return {"title_zh": title_zh or "", "abstract_zh": abstract_zh or ""}


def translate_long_text_google(translator, text: str) -> str:
    chunks = split_text(text, MAX_GOOGLE_CHARS)
    translated = [translator.translate(chunk) for chunk in chunks if chunk.strip()]
    return "\n\n".join(x for x in translated if x)


def split_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    chunks: list[str] = []
    current = ""
    for part in text.replace("\r\n", "\n").split(". "):
        sentence = part if part.endswith(".") else f"{part}."
        if len(current) + len(sentence) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def translate_with_deepseek(article: Article) -> dict:
    prompt_tpl = load_yaml(ROOT / "config" / "prompts.yaml")["translation"]
    prompt = (
        prompt_tpl.replace("{journal}", article.journal or "")
        .replace("{title_en}", article.title_en or "")
        .replace("{abstract_en}", article.abstract_en or "")
    )
    data, _raw = DeepSeekClient().json_chat(prompt)
    return data
