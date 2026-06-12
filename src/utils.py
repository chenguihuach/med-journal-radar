from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "articles.sqlite"
ENV_PATH = ROOT / ".env"


def load_env() -> None:
    load_dotenv(ENV_PATH)


def env_file_exists() -> bool:
    return ENV_PATH.exists()


def has_deepseek_api_key() -> bool:
    load_env()
    return bool(os.getenv("DEEPSEEK_API_KEY", "").strip())


def app_user_agent() -> str:
    load_env()
    return os.getenv("APP_USER_AGENT", "med-journal-radar/0.1")


def headers() -> dict[str, str]:
    return {"User-Agent": app_user_agent()}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"^(doi:\s*|https?://(dx\.)?doi\.org/)", "", value, flags=re.I)
    match = re.search(r"10\.\d{4,9}/\S+", value)
    return match.group(0).rstrip(").,;") if match else None


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_date(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d", "%d %b %Y", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
        m = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if m:
            return m.group(0)
        return text[:10] if len(text) >= 10 else text
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        return f"{value[0]:04d}-{value[1]:02d}-{value[2]:02d}"
    return None


def as_json_text(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2)
