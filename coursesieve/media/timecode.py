from __future__ import annotations


def sec_to_hms(seconds: float) -> str:
    total = max(0, int(seconds))
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def hms_to_sec(hms: str) -> int:
    parts = hms.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid timecode: {hms}")
    h, m, s = (int(p) for p in parts)
    return h * 3600 + m * 60 + s
