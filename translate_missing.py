from __future__ import annotations

import argparse
import os

from sqlalchemy import select

from src.db import get_session, init_db
from src.models import Article
from src.translator import translate_article
from src.utils import has_deepseek_api_key


def translate_missing(limit: int | None = None, provider: str | None = None) -> tuple[int, int]:
    if provider:
        os.environ["TRANSLATION_PROVIDER"] = provider
    init_db()
    ok = total = 0
    with get_session() as session:
        query = select(Article).where(Article.translation_status.in_(["not_translated", "failed"])).order_by(Article.created_at.desc())
        if limit:
            query = query.limit(limit)
        for article in session.execute(query).scalars():
            total += 1
            ok += int(translate_article(session, article))
    return total, ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--provider", choices=["google", "deepseek"], default=None)
    args = parser.parse_args()
    if (args.provider in (None, "deepseek")) and not has_deepseek_api_key():
        print("DEEPSEEK_API_KEY is not configured. Copy .env.example to .env and add your own key before translating.")
        raise SystemExit(1)
    total, ok = translate_missing(args.limit, args.provider)
    print(f"Translated {ok}/{total} articles.")
