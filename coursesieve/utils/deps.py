from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


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
            logger.debug("Resolved %s from vendor path: %s", name, candidate)
            return str(candidate)
    resolved = shutil.which(name)
    if resolved:
        logger.debug("Resolved %s from PATH: %s", name, resolved)
    else:
        logger.debug("Failed to resolve %s from vendor/PATH", name)
    return resolved


def probe_dependencies(enable_ocr: bool, vendor_root: Path | None = None) -> DependencyStatus:
    logger.info("Probing dependencies (enable_ocr=%s, vendor_root=%s)", enable_ocr, vendor_root)
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

    logger.info(
        "Dependency status: ffmpeg=%s, tesseract=%s, mpv=%s",
        ffmpeg or "missing",
        tesseract or "missing",
        mpv or "missing",
    )
    return DependencyStatus(ffmpeg=ffmpeg, tesseract=tesseract, mpv=mpv)
