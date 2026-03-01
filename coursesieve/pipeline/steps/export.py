from __future__ import annotations

import logging
from pathlib import Path

from coursesieve.media.timecode import hms_to_sec, sec_to_hms
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_json

logger = logging.getLogger(__name__)


def _collect_anchors(ctx: PipelineContext) -> list[tuple[str, str]]:
    index = read_json(ctx.cache.map_dir / "index.json")
    anchors: list[tuple[str, str]] = []
    for item in index:
        chunk = read_json(Path(item["path"]))
        for kp in chunk.get("key_points", []):
            title = str(kp.get("title", "要点"))
            t = str(kp.get("time_anchor", "00:00:00"))
            anchors.append((t, title))
        for ep in chunk.get("exam_points", []):
            point = str(ep.get("point", "考点"))
            t = str(ep.get("time_anchor", "00:00:00"))
            anchors.append((t, f"考点: {point[:32]}"))

    anchors.sort(key=lambda x: hms_to_sec(x[0]))
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for t, title in anchors:
        if t in seen:
            continue
        seen.add(t)
        deduped.append((t, title))
    logger.debug("Collected %d anchors (%d deduplicated)", len(anchors), len(deduped))
    return deduped


def run_export(ctx: PipelineContext) -> dict[str, str]:
    anchors = _collect_anchors(ctx)
    logger.info("Running export step with %d anchors", len(anchors))
    source_meta = read_json(ctx.cache.source_dir / "source.json")
    video_path = source_meta.get("video_path", "<video_path>")

    index_md = ctx.cache.final_dir / "index.md"
    ffmetadata = ctx.cache.final_dir / "chapters.ffmetadata"

    index_lines = ["# 回看索引", ""]
    for t, title in anchors:
        index_lines.append(f"- {title} ({t})")
        index_lines.append(f"  - `mpv \"{video_path}\" --start={t}`")

    md_lines = [";FFMETADATA1"]
    for i, (t, title) in enumerate(anchors):
        start_ms = hms_to_sec(t) * 1000
        if i + 1 < len(anchors):
            end_ms = hms_to_sec(anchors[i + 1][0]) * 1000 - 1
        else:
            end_ms = start_ms + 30_000
        if end_ms <= start_ms:
            end_ms = start_ms + 1_000
        md_lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start_ms}",
                f"END={end_ms}",
                f"title={title}",
            ]
        )

    index_md.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    ffmetadata.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    logger.info("Export outputs written: index=%s chapters=%s", index_md, ffmetadata)

    return {
        "index_md": str(index_md),
        "chapters_ffmetadata": str(ffmetadata),
        "video_path": str(video_path),
        "anchors": str(len(anchors)),
        "sample_timecode": sec_to_hms(0),
    }
