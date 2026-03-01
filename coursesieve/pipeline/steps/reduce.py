from __future__ import annotations

import logging
from pathlib import Path

from coursesieve.media.timecode import sec_to_hms
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_json, write_json

logger = logging.getLogger(__name__)


def _collect_chunks(map_index_path: Path) -> list[dict]:
    index = read_json(map_index_path)
    chunks: list[dict] = []
    for item in index:
        chunks.append(read_json(Path(item["path"])))
    logger.debug("Loaded %d map chunk summaries from %s", len(chunks), map_index_path)
    return chunks


def run_reduce(ctx: PipelineContext) -> dict[str, str]:
    map_index_path = ctx.cache.map_dir / "index.json"
    chunks = _collect_chunks(map_index_path)
    logger.info("Running reduce step with %d map chunks", len(chunks))

    key_points: list[dict] = []
    exam_points: list[dict] = []
    formulas: list[dict] = []
    patterns: list[dict] = []
    examples: list[dict] = []
    glossary: list[dict] = []
    uncertain: list[str] = []

    for ch in chunks:
        key_points.extend(ch.get("key_points", []))
        exam_points.extend(ch.get("exam_points", []))
        formulas.extend(ch.get("formulas", []))
        patterns.extend(ch.get("problem_patterns", []))
        examples.extend(ch.get("examples", []))
        glossary.extend(ch.get("glossary", []))
        uncertain.extend(ch.get("uncertain", []))
    logger.info(
        "Reduce aggregate counts: key_points=%d exam_points=%d formulas=%d patterns=%d examples=%d glossary=%d uncertain=%d",
        len(key_points),
        len(exam_points),
        len(formulas),
        len(patterns),
        len(examples),
        len(glossary),
        len(uncertain),
    )

    notes_path = ctx.cache.final_dir / "notes.md"
    review_path = ctx.cache.final_dir / "review_checklist.md"
    exam_path = ctx.cache.final_dir / "exam_points.md"
    anki_path = ctx.cache.final_dir / "anki.csv"
    merged_json = ctx.cache.final_dir / "reduced.json"

    notes_lines = ["# 冲刺笔记", ""]
    for i, kp in enumerate(key_points, start=1):
        notes_lines.append(f"## {i}. {kp.get('title', '要点')}")
        notes_lines.append(f"- 时间: {kp.get('time_anchor', '00:00:00')}")
        for bullet in kp.get("bullets", []):
            notes_lines.append(f"- {bullet}")
        notes_lines.append("")

    review_lines = ["# 复习清单", ""]
    for ep in exam_points:
        review_lines.append(
            f"- [{ep.get('level', '常考')}] {ep.get('point', '')} @ {ep.get('time_anchor', '00:00:00')}"
        )

    source_meta = read_json(ctx.cache.source_dir / "source.json")
    video_path = source_meta.get("video_path", "<video_path>")

    exam_lines = ["# 考点总表", ""]
    for ep in exam_points:
        anchor = ep.get("time_anchor", "00:00:00")
        exam_lines.append(f"- {ep.get('point', '')}")
        exam_lines.append(f"  - 级别: {ep.get('level', '常考')}")
        exam_lines.append(f"  - 时间: {anchor}")
        exam_lines.append(f"  - 跳转: `mpv \"{video_path}\" --start={anchor}`")

    anki_lines = ["front,back"]
    for g in glossary:
        front = str(g.get("term", "")).replace(",", " ")
        back = str(g.get("definition", "")).replace(",", " ")
        anki_lines.append(f"{front},{back}")

    notes_path.write_text("\n".join(notes_lines) + "\n", encoding="utf-8")
    review_path.write_text("\n".join(review_lines) + "\n", encoding="utf-8")
    exam_path.write_text("\n".join(exam_lines) + "\n", encoding="utf-8")
    anki_path.write_text("\n".join(anki_lines) + "\n", encoding="utf-8")

    write_json(
        merged_json,
        {
            "key_points": key_points,
            "exam_points": exam_points,
            "formulas": formulas,
            "problem_patterns": patterns,
            "examples": examples,
            "glossary": glossary,
            "uncertain": uncertain,
            "generated_at": sec_to_hms(0),
        },
    )
    logger.info(
        "Reduce outputs written: notes=%s checklist=%s exam=%s anki=%s reduced=%s",
        notes_path,
        review_path,
        exam_path,
        anki_path,
        merged_json,
    )

    return {
        "notes": str(notes_path),
        "review_checklist": str(review_path),
        "exam_points": str(exam_path),
        "anki": str(anki_path),
        "reduced_json": str(merged_json),
    }
