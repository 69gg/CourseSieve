from __future__ import annotations

from pathlib import Path

from coursesieve.asr.faster_whisper_backend import transcribe_to_files
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_json


def _resolve_audio_path(ctx: PipelineContext) -> Path:
    prep_meta = read_json(ctx.cache.prep_dir / "prep.json")
    return Path(prep_meta["audio_path"]).resolve()


def run_asr(ctx: PipelineContext) -> dict[str, str]:
    if ctx.config.asr_backend != "faster-whisper":
        raise RuntimeError(f"Unsupported asr backend: {ctx.config.asr_backend}")

    audio_path = _resolve_audio_path(ctx)
    transcript_json = ctx.cache.asr_dir / "transcript.json"
    transcript_srt = ctx.cache.asr_dir / "transcript.srt"

    transcribe_to_files(
        audio_path=audio_path,
        model_name=ctx.config.asr_model,
        language=ctx.config.lang,
        output_json=transcript_json,
        output_srt=transcript_srt,
    )
    return {
        "transcript_json": str(transcript_json),
        "transcript_srt": str(transcript_srt),
    }
