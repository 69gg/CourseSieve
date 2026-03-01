from __future__ import annotations

from coursesieve.media.timecode import sec_to_hms
from coursesieve.ocr.cleanup import similar
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_json, read_jsonl, write_jsonl


def run_fuse(ctx: PipelineContext) -> dict[str, str]:
    transcript = read_json(ctx.cache.asr_dir / "transcript.json")
    ocr_rows = read_jsonl(ctx.cache.ocr_dir / "ocr.jsonl")

    fused_rows: list[dict[str, object]] = []
    md_lines: list[str] = []

    delta = float(ctx.config.ocr_window_delta_sec)
    min_insert_gap = max(1, int(ctx.config.ocr_change_insert_min)) * 60
    last_insert_time = -1e9
    last_insert_text = ""

    for seg in transcript.get("segments", []):
        start = float(seg["start"])
        end = float(seg["end"])
        speech = str(seg.get("text", "")).strip()

        matched_texts: list[str] = []
        for row in ocr_rows:
            t = float(row["time_sec"])
            if start - delta <= t <= end + delta:
                text = str(row.get("text", "")).strip()
                if text and text not in matched_texts:
                    matched_texts.append(text)

        screen_text: list[str] = []
        if matched_texts:
            head = matched_texts[0]
            if (not similar(head, last_insert_text)) or (start - last_insert_time >= min_insert_gap):
                screen_text = matched_texts
                last_insert_text = head
                last_insert_time = start

        anchor = sec_to_hms(start)
        fused_rows.append(
            {
                "start": start,
                "end": end,
                "time_anchor": anchor,
                "speech": speech,
                "screen_text": screen_text,
            }
        )
        md_lines.append(f"[{sec_to_hms(start)} - {sec_to_hms(end)}] {speech}")
        for txt in screen_text:
            md_lines.append(f"[SCREEN @ {anchor}] {txt}")
        md_lines.append("")

    fused_jsonl = ctx.cache.fused_dir / "fused.jsonl"
    fused_md = ctx.cache.fused_dir / "fused.md"
    write_jsonl(fused_jsonl, fused_rows)
    fused_md.write_text("\n".join(md_lines), encoding="utf-8")
    return {"fused_jsonl": str(fused_jsonl), "fused_md": str(fused_md)}
