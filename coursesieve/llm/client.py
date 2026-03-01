from __future__ import annotations

import json
from dataclasses import dataclass, field
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAICompatClient:
    base_url: str
    api_key: str
    model: str
    timeout: float = 6000.0
    last_raw_response: dict | None = field(default=None, init=False, repr=False)
    last_raw_content: str | None = field(default=None, init=False, repr=False)
    last_response_id: str | None = field(default=None, init=False, repr=False)
    last_finish_reason: str | None = field(default=None, init=False, repr=False)
    last_usage: dict | None = field(default=None, init=False, repr=False)
    last_tool_call_count: int = field(default=0, init=False, repr=False)

    @staticmethod
    def _parse_json_object_from_text(raw: Any) -> dict | None:
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return None
        text = raw.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return None
        return None

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
        self.last_raw_response = data
        self.last_response_id = str(data.get("id", ""))
        self.last_usage = data.get("usage") if isinstance(data.get("usage"), dict) else None

        choice = data["choices"][0]
        self.last_finish_reason = str(choice.get("finish_reason", "")) if isinstance(choice, dict) else ""
        content = choice["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        self.last_raw_content = content
        parsed = json.loads(content)
        logger.debug(
            "OpenAI-compatible response parsed: id=%s finish_reason=%s usage=%s",
            self.last_response_id,
            self.last_finish_reason,
            self.last_usage,
        )
        return parsed

    def chat_json_with_tool(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
    ) -> dict:
        logger.debug(
            "Calling OpenAI-compatible API with tool call: base_url=%s model=%s tool=%s prompt_len=%d",
            self.base_url,
            self.model,
            tool_name,
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
            "stream": False,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_description,
                        "parameters": tool_schema,
                    },
                }
            ],
            # Thinking models on some gateways do not support forced function selection well.
            "tool_choice": "auto",
        }
        url = self.base_url.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        self.last_raw_response = data
        self.last_response_id = str(data.get("id", ""))
        self.last_usage = data.get("usage") if isinstance(data.get("usage"), dict) else None

        choice = data["choices"][0]
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
        self.last_finish_reason = str(choice.get("finish_reason", "")) if isinstance(choice, dict) else ""

        tool_calls = []
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls") or []
        if not tool_calls and isinstance(choice, dict):
            tool_calls = choice.get("tool_calls") or []
        if not tool_calls and isinstance(delta, dict):
            tool_calls = delta.get("tool_calls") or []
        self.last_tool_call_count = len(tool_calls)
        logger.debug(
            "LLM response meta: id=%s finish_reason=%s tool_calls=%d usage=%s",
            self.last_response_id,
            self.last_finish_reason,
            self.last_tool_call_count,
            self.last_usage,
        )

        if tool_calls:
            arguments = tool_calls[0].get("function", {}).get("arguments", "{}")
            if isinstance(arguments, dict):
                self.last_raw_content = json.dumps(arguments, ensure_ascii=False)
                logger.debug("Tool call response parsed from dict arguments")
                return arguments
            args_text = str(arguments).strip()
            self.last_raw_content = args_text
            if not args_text:
                raise RuntimeError(
                    "Tool call arguments are empty. "
                    f"raw_response={json.dumps(data, ensure_ascii=False)}"
                )
            parsed = json.loads(args_text)
            logger.debug("Tool call response parsed from JSON arguments")
            return parsed

        # Compatibility fallback: some thinking providers place JSON in content/reasoning fields.
        candidates: list[Any] = []
        if isinstance(message, dict):
            candidates.extend(
                [
                    message.get("content"),
                    message.get("reasoning_content"),
                    message.get("reasoning"),
                ]
            )
        if isinstance(choice, dict):
            candidates.extend(
                [
                    choice.get("content"),
                    choice.get("reasoning_content"),
                    choice.get("reasoning"),
                ]
            )
        if isinstance(delta, dict):
            candidates.extend(
                [
                    delta.get("content"),
                    delta.get("reasoning_content"),
                    delta.get("reasoning"),
                ]
            )

        for item in candidates:
            parsed_obj = self._parse_json_object_from_text(item)
            if isinstance(parsed_obj, dict):
                self.last_raw_content = json.dumps(parsed_obj, ensure_ascii=False)
                logger.warning(
                    "Model returned JSON object outside tool_calls; accepted as compatibility fallback"
                )
                return parsed_obj

        content_preview = ""
        for item in candidates:
            text = str(item).strip() if item is not None else ""
            if text:
                content_preview = text
                break
        self.last_raw_content = content_preview
        raise RuntimeError(
            "Model did not return tool_calls. "
            f"message_keys={list(message.keys()) if isinstance(message, dict) else type(message).__name__} "
            f"choice_keys={list(choice.keys()) if isinstance(choice, dict) else type(choice).__name__} "
            f"delta_keys={list(delta.keys()) if isinstance(delta, dict) else type(delta).__name__} "
            f"raw_content={content_preview} raw_response={json.dumps(data, ensure_ascii=False)}"
        )
