from __future__ import annotations

from collections import defaultdict

from coursesieve.llm.client import OpenAICompatClient
from coursesieve.llm.prompts import MAP_SYSTEM_PROMPT, build_map_user_prompt
from coursesieve.llm.schema import ChunkSummary
from coursesieve.media.timecode import sec_to_hms
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_jsonl, write_json


def _chunk_fused(rows: list[dict], chunk_sec: int) -> dict[int, list[dict]]:
    buckets: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        idx = int(float(row.get("start", 0.0)) // chunk_sec)
        buckets[idx].append(row)
    return dict(sorted(buckets.items(), key=lambda x: x[0]))


def _heuristic_summary(chunk_rows: list[dict]) -> ChunkSummary:
    key_points = []
    exam_points = []
    glossary = []
    for row in chunk_rows[:8]:
        speech = str(row.get("speech", "")).strip()
        if not speech:
            continue
        anchor = str(row.get("time_anchor", "00:00:00"))
        title = speech[:30] + ("..." if len(speech) > 30 else "")
        key_points.append({"title": title, "bullets": [speech[:120]], "time_anchor": anchor})
        if "注意" in speech or "易错" in speech or "重点" in speech:
            exam_points.append({"level": "常考", "point": speech[:100], "time_anchor": anchor})
        if "定义" in speech or "是指" in speech:
            glossary.append({"term": title[:20], "definition": speech[:100], "time_anchor": anchor})

    return ChunkSummary(
        key_points=key_points,
        exam_points=exam_points,
        glossary=glossary,
        uncertain=["Heuristic summary used (LLM unavailable or failed)."],
    )


def _rows_to_text(rows: list[dict]) -> str:
    lines: list[str] = []
    for row in rows:
        anchor = row.get("time_anchor", "00:00:00")
        lines.append(f"[{anchor}] {row.get('speech', '')}")
        for text in row.get("screen_text", []):
            lines.append(f"[SCREEN @ {anchor}] {text}")
    return "\n".join(lines)


def run_summarize(ctx: PipelineContext) -> dict[str, str]:
    rows = read_jsonl(ctx.cache.fused_dir / "fused.jsonl")
    chunk_sec = max(60, ctx.config.chunk_min * 60)
    chunked = _chunk_fused(rows, chunk_sec)

    client: OpenAICompatClient | None = None
    if (
        ctx.config.llm_provider == "openai_compat"
        and ctx.config.base_url
        and ctx.config.api_key
        and ctx.config.model
    ):
        client = OpenAICompatClient(
            base_url=ctx.config.base_url,
            api_key=ctx.config.api_key,
            model=ctx.config.model,
        )

    index: list[dict[str, object]] = []
    for idx, chunk_rows in chunked.items():
        start_sec = idx * chunk_sec
        end_sec = start_sec + chunk_sec
        chunk_name = f"chunk_{idx:03d}.json"
        chunk_path = ctx.cache.map_dir / chunk_name

        summary: ChunkSummary
        if client is None:
            summary = _heuristic_summary(chunk_rows)
        else:
            prompt = build_map_user_prompt(_rows_to_text(chunk_rows))
            last_error = ""
            parsed: ChunkSummary | None = None
            for _ in range(ctx.config.map_retry + 1):
                try:
                    payload = client.chat_json(system_prompt=MAP_SYSTEM_PROMPT, user_prompt=prompt)
                    parsed = ChunkSummary.model_validate(payload)
                    break
                except Exception as exc:
                    last_error = str(exc)
            if parsed is None:
                summary = _heuristic_summary(chunk_rows)
                summary.uncertain.append(f"LLM parse failed: {last_error[:200]}")
            else:
                summary = parsed

        write_json(chunk_path, summary.model_dump())
        index.append(
            {
                "chunk": idx,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "start": sec_to_hms(start_sec),
                "end": sec_to_hms(end_sec),
                "path": str(chunk_path),
            }
        )

    map_index_path = ctx.cache.map_dir / "index.json"
    write_json(map_index_path, index)
    return {"map_index": str(map_index_path)}
