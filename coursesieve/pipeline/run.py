from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from coursesieve.config import RuntimeConfig
from coursesieve.store.cache import CacheLayout
from coursesieve.store.manifest import ManifestStore
from coursesieve.utils.hashing import build_video_id, stable_hash

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineContext:
    config: RuntimeConfig
    video_id: str
    cache: CacheLayout
    manifest: ManifestStore
    source_video: Path | None = None


def make_context(config: RuntimeConfig) -> PipelineContext:
    video_id = build_video_id(config.source_input, config.semantic_hash_payload())
    cache_root = config.out_dir / ".cache" / video_id
    cache = CacheLayout(cache_root)
    cache.ensure()
    manifest = ManifestStore(cache.manifest_path)
    return PipelineContext(config=config, video_id=video_id, cache=cache, manifest=manifest)


def run_step(
    ctx: PipelineContext,
    step: str,
    params: dict[str, Any],
    fn: Callable[[], dict[str, str]],
) -> dict[str, str]:
    p_hash = stable_hash(params)
    if ctx.manifest.is_step_fresh(step, p_hash):
        logger.info("[%s] cache hit, skipping", step)
        return ctx.manifest.get_step_outputs(step)

    logger.info("[%s] running", step)
    start = time.time()
    outputs = fn()
    duration = time.time() - start
    ctx.manifest.mark_step(step=step, params_hash=p_hash, outputs=outputs, duration_sec=duration)
    logger.info("[%s] done in %.1fs", step, duration)
    return outputs
