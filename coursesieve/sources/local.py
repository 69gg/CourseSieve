from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_local_video(path_like: str) -> Path:
    p = Path(path_like).expanduser().resolve()
    logger.info("Resolving local video: %s", p)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Local video file not found: {p}")
    logger.debug("Local video resolved: %s", p)
    return p
