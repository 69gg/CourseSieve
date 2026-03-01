from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from coursesieve.media.ffmpeg import extract_fallback_frames, probe_duration
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_json, write_jsonl

_SHOWINFO_PTS = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")
logger = logging.getLogger(__name__)


def _resolve_video_path(ctx: PipelineContext) -> Path:
    prep_meta = read_json(ctx.cache.prep_dir / "prep.json")
    video_path = Path(prep_meta["video_path"]).resolve()
    logger.debug("Resolved video path for frames step: %s", video_path)
    return video_path


def _extract_scene_frames_with_time(
    ffmpeg_bin: str, video_path: Path, out_dir: Path, threshold: float
) -> list[tuple[Path, float]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "scene_%06d.png"
    logger.info(
        "Extracting scene frames with showinfo: video=%s threshold=%s",
        video_path,
        threshold,
    )
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"select=gt(scene\\,{threshold}),showinfo",
        "-vsync",
        "vfr",
        str(pattern),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"scene frame extraction failed: {proc.stderr.strip()}")

    times = [float(m.group(1)) for m in _SHOWINFO_PTS.finditer(proc.stderr)]
    frames = sorted(out_dir.glob("scene_*.png"))
    logger.info("Scene extraction produced %d frames and %d timestamps", len(frames), len(times))
    if len(times) < len(frames):
        duration = probe_duration(ffmpeg_bin, video_path)
        missing = len(frames) - len(times)
        if missing > 0:
            step = duration / max(1, len(frames) + 1)
            times.extend([step * (len(times) + i + 1) for i in range(missing)])
            logger.warning(
                "Scene timestamps missing for %d frames, generated estimated timestamps", missing
            )
    return list(zip(frames, times[: len(frames)]))


def run_frames(ctx: PipelineContext, ffmpeg_bin: str) -> dict[str, str]:
    video_path = _resolve_video_path(ctx)
    logger.info(
        "Running frames step: scene_threshold=%s fallback_sec=%s",
        ctx.config.scene_threshold,
        ctx.config.frame_fallback_sec,
    )
    scene_dir = ctx.cache.frames_dir / "scene"
    fallback_dir = ctx.cache.frames_dir / "fallback"

    scene_items = _extract_scene_frames_with_time(
        ffmpeg_bin=ffmpeg_bin,
        video_path=video_path,
        out_dir=scene_dir,
        threshold=ctx.config.scene_threshold,
    )

    fallback_frames = extract_fallback_frames(
        ffmpeg_bin=ffmpeg_bin,
        video_path=video_path,
        out_dir=fallback_dir,
        interval_sec=ctx.config.frame_fallback_sec,
    )
    fallback_items = [
        (frame, (idx - 1) * float(ctx.config.frame_fallback_sec))
        for idx, frame in enumerate(fallback_frames, start=1)
    ]
    logger.info("Fallback extraction produced %d frames", len(fallback_items))

    rows: list[dict[str, object]] = []
    seen: set[int] = set()
    merged = [
        *((p, t, "scene") for p, t in scene_items),
        *((p, t, "fallback") for p, t in fallback_items),
    ]
    for frame_path, t, strategy in sorted(merged, key=lambda x: x[1]):
        sec_key = int(round(float(t)))
        if sec_key in seen:
            continue
        seen.add(sec_key)
        rows.append(
            {
                "time_sec": round(float(t), 3),
                "strategy": strategy,
                "frame_path": str(frame_path.resolve()),
            }
        )

    frames_jsonl = ctx.cache.frames_dir / "frames.jsonl"
    write_jsonl(frames_jsonl, rows)
    logger.info(
        "Frames step completed: merged=%d deduped=%d output=%s",
        len(merged),
        len(rows),
        frames_jsonl,
    )
    return {
        "frames_jsonl": str(frames_jsonl),
        "scene_dir": str(scene_dir),
        "fallback_dir": str(fallback_dir),
    }
