from __future__ import annotations

import logging
from pathlib import Path

from coursesieve.pipeline.run import PipelineContext
from coursesieve.sources.bilibili import fetch_bilibili, looks_like_bili
from coursesieve.sources.local import resolve_local_video
from coursesieve.utils.io import write_json

logger = logging.getLogger(__name__)


def run_fetch(ctx: PipelineContext) -> dict[str, str]:
    source_meta_path = ctx.cache.source_dir / "source.json"
    logger.info("Running fetch step for input: %s", ctx.config.source_input)

    if looks_like_bili(ctx.config.source_input):
        logger.info("Input detected as Bilibili source")
        target_dir = ctx.config.download_dir or ctx.cache.source_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        result = fetch_bilibili(
            source=ctx.config.source_input,
            save_path=target_dir,
            cookie=ctx.config.bili_cookie,
            prefer_quality=ctx.config.bili_quality,
            timeout=ctx.config.bili_timeout,
            overwrite=ctx.config.bili_overwrite,
        )
        video_path = result.local_path
        payload = {
            "source_type": "bilibili",
            "input": ctx.config.source_input,
            "video_path": str(video_path),
            "meta": result.payload,
        }
    else:
        logger.info("Input detected as local source")
        video_path = resolve_local_video(ctx.config.source_input)
        payload = {
            "source_type": "local",
            "input": ctx.config.source_input,
            "video_path": str(video_path),
            "meta": {},
        }

    write_json(source_meta_path, payload)
    ctx.source_video = Path(payload["video_path"]).resolve()
    logger.info("Fetch step completed: video_path=%s", ctx.source_video)
    return {"video_path": str(ctx.source_video), "source_meta": str(source_meta_path)}
