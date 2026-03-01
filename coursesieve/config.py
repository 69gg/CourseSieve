from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RuntimeConfig:
    source_input: str
    out_dir: Path
    lang: str = "zh"
    ocr_lang: str = "chi_sim+eng"
    chunk_min: int = 12
    scene_threshold: float = 0.35
    frame_fallback_sec: int = 30
    asr_backend: str = "faster-whisper"
    asr_model: str = "medium"
    llm_provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    player: str = "mpv"
    bili_cookie: str = ""
    bili_quality: int = 80
    bili_timeout: float = 30.0
    bili_overwrite: bool = True
    download_dir: Path | None = None
    ocr_window_delta_sec: float = 2.0
    ocr_change_insert_min: int = 3
    map_retry: int = 2
    max_workers: int = 2

    def semantic_hash_payload(self) -> dict[str, Any]:
        # Keep only options that affect semantic outputs.
        return {
            "lang": self.lang,
            "ocr_lang": self.ocr_lang,
            "chunk_min": self.chunk_min,
            "scene_threshold": self.scene_threshold,
            "frame_fallback_sec": self.frame_fallback_sec,
            "asr_backend": self.asr_backend,
            "asr_model": self.asr_model,
            "llm_provider": self.llm_provider,
            "model": self.model,
            "ocr_window_delta_sec": self.ocr_window_delta_sec,
            "ocr_change_insert_min": self.ocr_change_insert_min,
        }
