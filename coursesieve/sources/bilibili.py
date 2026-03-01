from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FetchResult:
    local_path: Path
    payload: dict[str, Any]


def looks_like_bili(source: str) -> bool:
    s = source.strip().lower()
    return (
        s.startswith("bv")
        or s.startswith("av")
        or "bilibili.com/video/" in s
        or "b23.tv/" in s
    )


def fetch_bilibili(
    source: str,
    save_path: Path,
    cookie: str,
    prefer_quality: int,
    timeout: float,
    overwrite: bool,
) -> FetchResult:
    try:
        from oh_my_bilibili import fetch
    except Exception as exc:  # pragma: no cover - import path depends on env
        raise RuntimeError("oh-my-bilibili is not installed or failed to import") from exc

    save_path.parent.mkdir(parents=True, exist_ok=True)
    result = fetch(
        source,
        save_path=str(save_path),
        cookie=cookie,
        prefer_quality=prefer_quality,
        timeout=timeout,
        overwrite=overwrite,
    )
    payload = {
        "title": getattr(result, "title", None),
        "url": getattr(result, "url", None),
        "quality_label": getattr(result, "quality_label", None),
        "path": str(getattr(result, "path", save_path)),
    }
    local_path = Path(payload["path"]).expanduser().resolve()
    return FetchResult(local_path=local_path, payload=payload)
