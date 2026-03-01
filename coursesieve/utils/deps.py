from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DependencyStatus:
    ffmpeg: str | None
    tesseract: str | None
    mpv: str | None


def _resolve_binary(name: str, vendor_dir: Path | None = None) -> str | None:
    if vendor_dir is not None:
        exe = f"{name}.exe" if os.name == "nt" else name
        candidate = vendor_dir / exe
        if candidate.exists():
            return str(candidate)
    return shutil.which(name)


def probe_dependencies(enable_ocr: bool, vendor_root: Path | None = None) -> DependencyStatus:
    ffmpeg = _resolve_binary("ffmpeg", (vendor_root / "ffmpeg") if vendor_root else None)
    tesseract = _resolve_binary("tesseract", (vendor_root / "tesseract") if vendor_root else None)
    mpv = _resolve_binary("mpv", (vendor_root / "mpv") if vendor_root else None)

    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found. Install ffmpeg or provide vendor/ffmpeg/ffmpeg(.exe).")
    if enable_ocr and tesseract is None:
        raise RuntimeError(
            "tesseract not found but OCR is enabled. Install tesseract or provide "
            "vendor/tesseract/tesseract(.exe)."
        )

    return DependencyStatus(ffmpeg=ffmpeg, tesseract=tesseract, mpv=mpv)
