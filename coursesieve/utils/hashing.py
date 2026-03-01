from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_video_id(source: str, semantic_options: dict[str, Any]) -> str:
    return stable_hash({"source": source, "semantic_options": semantic_options})
