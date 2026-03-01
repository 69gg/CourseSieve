from __future__ import annotations

from collections import defaultdict
import json
import logging
from pathlib import Path
import time
from typing import Any

from coursesieve.llm.client import OpenAICompatClient
from coursesieve.llm.prompts import MAP_SYSTEM_PROMPT, build_map_user_prompt
from coursesieve.llm.schema import ChunkSummary
from coursesieve.media.timecode import sec_to_hms
from coursesieve.pipeline.run import PipelineContext
from coursesieve.utils.io import read_jsonl, write_json

logger = logging.getLogger(__name__)
_MAP_TOOL_NAME = "emit_chunk_summary"
_MAP_TOOL_DESCRIPTION = "Emit chunk summary strictly following the required schema."
_MAP_TOOL_SCHEMA = ChunkSummary.model_json_schema()


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


def _is_empty_summary(summary: ChunkSummary) -> bool:
    return (
        not summary.key_points
        and not summary.exam_points
        and not summary.formulas
        and not summary.problem_patterns
        and not summary.examples
        and not summary.glossary
        and not summary.uncertain
    )


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_list_str(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            text = _to_str(item)
            if text:
                out.append(text)
        return out
    text = _to_str(value)
    return [text] if text else []


def _extract_time_anchor(item: dict[str, Any]) -> str:
    return (
        _to_str(item.get("time_anchor"))
        or _to_str(item.get("anchor"))
        or _to_str(item.get("timestamp"))
        or "00:00:00"
    )


def _extract_content(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        text = _to_str(item.get(key))
        if text:
            return text
    return ""


def _normalize_chunk_payload(payload: Any) -> tuple[dict[str, Any], bool]:
    if not isinstance(payload, dict):
        return {"uncertain": [f"Unexpected payload type: {type(payload).__name__}"]}, True

    adapted = False
    normalized: dict[str, Any] = {
        "key_points": [],
        "exam_points": [],
        "formulas": [],
        "problem_patterns": [],
        "examples": [],
        "glossary": [],
        "uncertain": [],
    }

    for raw in payload.get("key_points", []):
        item = raw if isinstance(raw, dict) else {"content": raw}
        title = _extract_content(item, "title", "content", "point", "text")
        bullets = _to_list_str(item.get("bullets") or item.get("points") or item.get("details"))
        if not bullets and title:
            bullets = [title]
        normalized["key_points"].append(
            {
                "title": title or "未命名要点",
                "bullets": bullets,
                "time_anchor": _extract_time_anchor(item),
            }
        )
        if "title" not in item and ("content" in item or "point" in item):
            adapted = True

    for raw in payload.get("exam_points", []):
        item = raw if isinstance(raw, dict) else {"content": raw}
        point = _extract_content(item, "point", "content", "title", "text")
        normalized["exam_points"].append(
            {
                "level": _extract_content(item, "level") or "常考",
                "point": point or "未命名考点",
                "time_anchor": _extract_time_anchor(item),
            }
        )
        if "point" not in item and "content" in item:
            adapted = True

    for raw in payload.get("formulas", []):
        item = raw if isinstance(raw, dict) else {"content": raw}
        expr = _extract_content(item, "expr", "formula", "content", "title")
        meaning = _extract_content(item, "meaning", "explain", "content")
        normalized["formulas"].append(
            {
                "expr": expr or "未命名公式",
                "meaning": meaning or expr or "待补充",
                "pitfalls": _extract_content(item, "pitfalls", "warning", "mistakes"),
                "time_anchor": _extract_time_anchor(item),
            }
        )
        if "expr" not in item and ("formula" in item or "content" in item):
            adapted = True

    for raw in payload.get("problem_patterns", []):
        item = raw if isinstance(raw, dict) else {"content": raw}
        trigger = _extract_content(item, "trigger", "content", "title")
        method = _extract_content(item, "method", "approach", "content")
        steps = _to_list_str(item.get("steps") or item.get("procedure"))
        normalized["problem_patterns"].append(
            {
                "trigger": trigger or "未命名题型",
                "method": method or trigger or "待补充",
                "steps": steps,
                "time_anchor": _extract_time_anchor(item),
            }
        )
        if "trigger" not in item and "content" in item:
            adapted = True

    for raw in payload.get("examples", []):
        item = raw if isinstance(raw, dict) else {"content": raw}
        prompt = _extract_content(item, "prompt", "question", "content", "title")
        solution = _extract_content(item, "skeleton_solution", "solution", "method")
        normalized["examples"].append(
            {
                "prompt": prompt or "未命名例题",
                "skeleton_solution": solution or "待补充",
                "time_anchor": _extract_time_anchor(item),
            }
        )
        if "prompt" not in item and "content" in item:
            adapted = True

    for raw in payload.get("glossary", []):
        item = raw if isinstance(raw, dict) else {"content": raw}
        term = _extract_content(item, "term", "title")
        definition = _extract_content(item, "definition", "content", "desc")
        if not term and definition:
            if "：" in definition:
                maybe_term, maybe_def = definition.split("：", 1)
            elif ":" in definition:
                maybe_term, maybe_def = definition.split(":", 1)
            else:
                maybe_term, maybe_def = definition[:12], definition
            term = maybe_term.strip() or "术语"
            definition = maybe_def.strip() or definition
            adapted = True
        normalized["glossary"].append(
            {
                "term": term or "术语",
                "definition": definition or "待补充",
                "time_anchor": _extract_time_anchor(item),
            }
        )
        if "term" not in item and "content" in item:
            adapted = True

    for raw in payload.get("uncertain", []):
        if isinstance(raw, dict):
            text = _extract_content(raw, "content", "text", "note")
            if not text:
                text = json.dumps(raw, ensure_ascii=False)
            normalized["uncertain"].append(text)
            adapted = True
        else:
            text = _to_str(raw)
            if text:
                normalized["uncertain"].append(text)

    return normalized, adapted


def _write_debug_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_summarize(ctx: PipelineContext) -> dict[str, str]:
    rows = read_jsonl(ctx.cache.fused_dir / "fused.jsonl")
    chunk_sec = max(60, ctx.config.chunk_min * 60)
    chunked = _chunk_fused(rows, chunk_sec)
    debug_dir = ctx.cache.map_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Running summarize step: fused_rows=%d chunk_sec=%d chunks=%d map_retry=%d debug_dir=%s",
        len(rows),
        chunk_sec,
        len(chunked),
        ctx.config.map_retry,
        debug_dir,
    )

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
        logger.info("Summarize step using LLM provider: %s", ctx.config.llm_provider)
    else:
        logger.warning("Summarize step running in heuristic mode (LLM not configured)")

    index: list[dict[str, object]] = []
    for idx, chunk_rows in chunked.items():
        start_sec = idx * chunk_sec
        end_sec = start_sec + chunk_sec
        chunk_name = f"chunk_{idx:03d}.json"
        chunk_path = ctx.cache.map_dir / chunk_name
        logger.info(
            "Summarizing chunk %03d: range=%s-%s rows=%d",
            idx,
            sec_to_hms(start_sec),
            sec_to_hms(end_sec),
            len(chunk_rows),
        )

        summary: ChunkSummary
        if client is None:
            summary = _heuristic_summary(chunk_rows)
            logger.debug("Chunk %03d summarized via heuristic", idx)
        else:
            prompt = build_map_user_prompt(_rows_to_text(chunk_rows))
            logger.debug("Chunk %03d prompt length=%d chars", idx, len(prompt))
            last_error = ""
            parsed: ChunkSummary | None = None
            for attempt in range(1, ctx.config.map_retry + 2):
                t0 = time.time()
                try:
                    logger.debug("Chunk %03d LLM attempt %d", idx, attempt)
                    payload = client.chat_json_with_tool(
                        system_prompt=MAP_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        tool_name=_MAP_TOOL_NAME,
                        tool_description=_MAP_TOOL_DESCRIPTION,
                        tool_schema=_MAP_TOOL_SCHEMA,
                    )
                    normalized_payload, adapted = _normalize_chunk_payload(payload)
                    if adapted:
                        logger.warning("Chunk %03d applied schema normalization for LLM payload", idx)
                        logger.debug(
                            "Chunk %03d normalized payload: %s",
                            idx,
                            json.dumps(normalized_payload, ensure_ascii=False),
                        )
                    _write_debug_file(
                        debug_dir / f"chunk_{idx:03d}_attempt_{attempt}_raw_response.json",
                        json.dumps(client.last_raw_response, ensure_ascii=False, indent=2),
                    )
                    _write_debug_file(
                        debug_dir / f"chunk_{idx:03d}_attempt_{attempt}_normalized_payload.json",
                        json.dumps(normalized_payload, ensure_ascii=False, indent=2),
                    )
                    parsed = ChunkSummary.model_validate(normalized_payload)
                    logger.info(
                        "Chunk %03d attempt %d succeeded in %.2fs (finish_reason=%s, tool_calls=%d)",
                        idx,
                        attempt,
                        time.time() - t0,
                        client.last_finish_reason,
                        client.last_tool_call_count,
                    )
                    break
                except Exception as exc:
                    last_error = str(exc)
                    _write_debug_file(
                        debug_dir / f"chunk_{idx:03d}_attempt_{attempt}_raw_response.json",
                        json.dumps(client.last_raw_response, ensure_ascii=False, indent=2),
                    )
                    _write_debug_file(
                        debug_dir / f"chunk_{idx:03d}_attempt_{attempt}_raw_content.txt",
                        client.last_raw_content or "",
                    )
                    logger.warning(
                        "Chunk %03d attempt %d failed in %.2fs: %s",
                        idx,
                        attempt,
                        time.time() - t0,
                        last_error,
                    )
                    logger.warning(
                        "Chunk %03d response meta: id=%s finish_reason=%s tool_calls=%d usage=%s",
                        idx,
                        client.last_response_id,
                        client.last_finish_reason,
                        client.last_tool_call_count,
                        json.dumps(client.last_usage, ensure_ascii=False),
                    )
            if parsed is None:
                summary = _heuristic_summary(chunk_rows)
                summary.uncertain.append(f"LLM parse failed: {last_error[:200]}")
                logger.warning("Chunk %03d fallback to heuristic summary", idx)
            else:
                summary = parsed
                if _is_empty_summary(summary):
                    logger.warning(
                        "Chunk %03d LLM returned empty summary. raw_content=%s raw_response=%s",
                        idx,
                        client.last_raw_content,
                        json.dumps(client.last_raw_response, ensure_ascii=False),
                    )

        write_json(chunk_path, summary.model_dump())
        logger.debug("Chunk summary written: %s", chunk_path)
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
    logger.info("Summarize step completed: map index=%s", map_index_path)
    return {"map_index": str(map_index_path)}
