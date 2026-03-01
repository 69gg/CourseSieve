from __future__ import annotations

import json
from dataclasses import dataclass
import logging
from pathlib import Path

from coursesieve.media.timecode import sec_to_hms

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Segment:
    start: float
    end: float
    text: str


def _write_srt(segments: list[Segment], output_srt: Path) -> None:
    logger.debug("Writing SRT with %d segments to %s", len(segments), output_srt)
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = sec_to_hms(seg.start).replace(":", ":", 2) + ",000"
        end = sec_to_hms(seg.end).replace(":", ":", 2) + ",000"
        lines.extend([str(i), f"{start} --> {end}", seg.text.strip(), ""])
    output_srt.write_text("\n".join(lines), encoding="utf-8")


def transcribe_to_files(
    audio_path: Path,
    model_name: str,
    language: str,
    output_json: Path,
    output_srt: Path,
) -> list[Segment]:
    logger.info(
        "Starting ASR transcription: audio=%s model=%s lang=%s",
        audio_path,
        model_name,
        language,
    )
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("faster-whisper is not installed") from exc

    logger.debug("Loading Whisper model: %s", model_name)
    model = WhisperModel(model_name, device="auto", compute_type="auto")
    segments_raw, _ = model.transcribe(str(audio_path), language=language)

    segments: list[Segment] = []
    for seg in segments_raw:
        segments.append(Segment(start=float(seg.start), end=float(seg.end), text=seg.text.strip()))
    logger.info("ASR transcription completed with %d segments", len(segments))

    payload = {"segments": [s.__dict__ for s in segments]}
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_srt(segments, output_srt)
    logger.info("ASR outputs written: json=%s srt=%s", output_json, output_srt)
    return segments
