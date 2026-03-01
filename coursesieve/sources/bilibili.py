from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
    logger.info(
        "Fetching Bilibili source: quality=%s timeout=%.1fs overwrite=%s",
        prefer_quality,
        timeout,
        overwrite,
    )
    try:
        from oh_my_bilibili import fetch
    except Exception as exc:  # pragma: no cover - import path depends on env
        raise RuntimeError("oh-my-bilibili is not installed or failed to import") from exc

    save_path.parent.mkdir(parents=True, exist_ok=True)
    logger.debug("Bilibili save path: %s", save_path)
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
    logger.info(
        "Bilibili fetch completed: title=%s path=%s",
        payload.get("title"),
        local_path,
    )
    return FetchResult(local_path=local_path, payload=payload)
