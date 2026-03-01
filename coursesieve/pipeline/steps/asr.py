from __future__ import annotations

import logging
from pathlib import Path

from coursesieve.asr.faster_whisper_backend import transcribe_to_files
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_json

logger = logging.getLogger(__name__)


def _resolve_audio_path(ctx: PipelineContext) -> Path:
    prep_meta = read_json(ctx.cache.prep_dir / "prep.json")
    audio_path = Path(prep_meta["audio_path"]).resolve()
    logger.debug("Resolved audio path from prep metadata: %s", audio_path)
    return audio_path


def run_asr(ctx: PipelineContext) -> dict[str, str]:
    if ctx.config.asr_backend != "faster-whisper":
        raise RuntimeError(f"Unsupported asr backend: {ctx.config.asr_backend}")

    audio_path = _resolve_audio_path(ctx)
    logger.info(
        "Running ASR step: backend=%s model=%s lang=%s",
        ctx.config.asr_backend,
        ctx.config.asr_model,
        ctx.config.lang,
    )
    transcript_json = ctx.cache.asr_dir / "transcript.json"
    transcript_srt = ctx.cache.asr_dir / "transcript.srt"

    segments = transcribe_to_files(
        audio_path=audio_path,
        model_name=ctx.config.asr_model,
        language=ctx.config.lang,
        output_json=transcript_json,
        output_srt=transcript_srt,
    )
    logger.info("ASR step completed with %d segments", len(segments))
    return {
        "transcript_json": str(transcript_json),
        "transcript_srt": str(transcript_srt),
    }
