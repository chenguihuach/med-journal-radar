from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from .utils import load_env


class LLMError(RuntimeError):
    pass


class JSONParseError(LLMError):
    def __init__(self, message: str, raw_response: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response


class DeepSeekClient:
    def __init__(self) -> None:
        load_env()
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        if not self.api_key or not self.api_key.strip():
            raise LLMError("DEEPSEEK_API_KEY is not configured.")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def json_chat(self, prompt: str) -> tuple[dict[str, Any], str]:
        last_error: Exception | None = None
        for _ in range(2):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "You return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw = resp.choices[0].message.content or "{}"
                return parse_json(raw), raw
            except JSONParseError:
                raise
            except Exception as exc:
                last_error = exc
        raise LLMError(str(last_error))


def parse_json(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
    raise JSONParseError("Unable to parse JSON from model response.", raw)
