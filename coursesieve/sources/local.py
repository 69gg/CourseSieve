from __future__ import annotations

from pathlib import Path


def resolve_local_video(path_like: str) -> Path:
    p = Path(path_like).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Local video file not found: {p}")
    return p
