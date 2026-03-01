from __future__ import annotations

from pathlib import Path

from coursesieve.ocr.cleanup import looks_like_noise, normalize_text, similar
from coursesieve.ocr.tesseract import ocr_image
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_jsonl, write_jsonl


def run_ocr(ctx: PipelineContext, tesseract_cmd: str | None) -> dict[str, str]:
    frames = read_jsonl(ctx.cache.frames_dir / "frames.jsonl")
    raw_rows: list[dict[str, object]] = []

    for row in frames:
        frame_path = row["frame_path"]
        text, conf = ocr_image(
            image_path=Path(frame_path),
            lang=ctx.config.ocr_lang,
            tesseract_cmd=tesseract_cmd,
        )
        text = normalize_text(text)
        if looks_like_noise(text):
            continue
        raw_rows.append(
            {
                "time_sec": row["time_sec"],
                "text": text,
                "conf": conf,
                "frame_path": frame_path,
            }
        )

    merged: list[dict[str, object]] = []
    for item in raw_rows:
        if not merged:
            merged.append(item)
            continue
        prev = merged[-1]
        if similar(str(prev["text"]), str(item["text"])):
            continue
        merged.append(item)

    out_path = ctx.cache.ocr_dir / "ocr.jsonl"
    write_jsonl(out_path, merged)
    return {"ocr_jsonl": str(out_path)}
