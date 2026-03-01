from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CacheLayout:
    root: Path

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def prep_dir(self) -> Path:
        return self.root / "prep"

    @property
    def asr_dir(self) -> Path:
        return self.root / "asr"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def ocr_dir(self) -> Path:
        return self.root / "ocr"

    @property
    def fused_dir(self) -> Path:
        return self.root / "fused"

    @property
    def map_dir(self) -> Path:
        return self.root / "map"

    @property
    def final_dir(self) -> Path:
        return self.root / "final"

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def ensure(self) -> None:
        for folder in [
            self.root,
            self.source_dir,
            self.prep_dir,
            self.asr_dir,
            self.frames_dir,
            self.ocr_dir,
            self.fused_dir,
            self.map_dir,
            self.final_dir,
        ]:
            folder.mkdir(parents=True, exist_ok=True)
