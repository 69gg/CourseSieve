from __future__ import annotations

import re

from rapidfuzz import fuzz


def looks_like_noise(text: str, min_len: int = 6) -> bool:
    t = text.strip()
    if len(t) < min_len:
        return True
    total = len(t)
    bad = sum(1 for ch in t if ch in "@#$%^&*_+=~`|\\")
    return total > 0 and bad / total > 0.35


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similar(a: str, b: str, threshold: int = 90) -> bool:
    if not a or not b:
        return False
    return fuzz.ratio(a, b) >= threshold
