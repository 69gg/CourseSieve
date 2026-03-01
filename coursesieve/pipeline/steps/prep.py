from __future__ import annotations

import logging
from pathlib import Path

from coursesieve.media.ffmpeg import extract_audio, probe_duration, split_audio
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_json, write_json

logger = logging.getLogger(__name__)


def _resolve_video_path(ctx: PipelineContext) -> Path:
    if ctx.source_video is not None:
        logger.debug("Using in-memory source video path: %s", ctx.source_video)
        return ctx.source_video
    source_meta = read_json(ctx.cache.source_dir / "source.json")
    video_path = Path(source_meta["video_path"]).resolve()
    logger.debug("Loaded source video path from metadata: %s", video_path)
    return video_path


def run_prep(ctx: PipelineContext, ffmpeg_bin: str) -> dict[str, str]:
    video_path = _resolve_video_path(ctx)
    logger.info("Running prep step: video=%s ffmpeg=%s", video_path, ffmpeg_bin)
    audio_path = ctx.cache.prep_dir / "audio_16k_mono.wav"
    chunks_dir = ctx.cache.prep_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    extract_audio(ffmpeg_bin, video_path, audio_path)
    chunk_sec = max(60, ctx.config.chunk_min * 60)
    chunks = split_audio(ffmpeg_bin, audio_path, chunks_dir, chunk_sec)

    duration = probe_duration(ffmpeg_bin, video_path)
    logger.info(
        "Prep generated audio and chunks: duration=%.2fs chunk_sec=%s chunks=%d",
        duration,
        chunk_sec,
        len(chunks),
    )
    prep_meta = {
        "video_path": str(video_path),
        "audio_path": str(audio_path),
        "chunk_sec": chunk_sec,
        "duration_sec": duration,
        "chunks": [str(c) for c in chunks],
    }
    prep_meta_path = ctx.cache.prep_dir / "prep.json"
    write_json(prep_meta_path, prep_meta)
    logger.debug("Prep metadata written: %s", prep_meta_path)

    return {
        "video_path": str(video_path),
        "audio_path": str(audio_path),
        "prep_meta": str(prep_meta_path),
        "chunks_dir": str(chunks_dir),
    }
