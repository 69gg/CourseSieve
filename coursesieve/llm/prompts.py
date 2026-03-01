from __future__ import annotations

MAP_SYSTEM_PROMPT = (
    "你是课程复习助理。基于输入的课堂语料（口播+屏幕文字），"
    "输出严格 JSON，字段必须匹配指定 schema，且每条结论必须带 time_anchor (HH:MM:SS)。"
    "不确定时放到 uncertain。不要输出 JSON 之外文本。"
)


def build_map_user_prompt(chunk_text: str) -> str:
    return (
        "请总结以下课程片段，提取要点/考点/公式/题型/术语。"
        "每条都给出 time_anchor。\n\n"
        f"语料:\n{chunk_text}\n"
    )


REDUCE_SYSTEM_PROMPT = (
    "你是课程冲刺整理器。请将多个 chunk 的结构化总结整合为最终复习资料。"
)
