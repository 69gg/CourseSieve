from __future__ import annotations

import json
from dataclasses import dataclass
import logging

import httpx

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAICompatClient:
    base_url: str
    api_key: str
    model: str
    timeout: float = 120.0

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        logger.debug(
            "Calling OpenAI-compatible API: base_url=%s model=%s prompt_len=%d",
            self.base_url,
            self.model,
            len(user_prompt),
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        url = self.base_url.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        parsed = json.loads(content)
        logger.debug("OpenAI-compatible response parsed successfully")
        return parsed
