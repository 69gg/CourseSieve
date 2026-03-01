from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_ffmpeg(ffmpeg_bin: str, args: list[str]) -> None:
    cmd = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()}")


def extract_audio(ffmpeg_bin: str, video_path: Path, audio_path: Path) -> None:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ffmpeg_bin,
        [
            "-y",
            "-i",
            str(video_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            str(audio_path),
        ],
    )


def split_audio(ffmpeg_bin: str, audio_path: Path, out_dir: Path, chunk_sec: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "chunk_%03d.wav"
    run_ffmpeg(
        ffmpeg_bin,
        [
            "-y",
            "-i",
            str(audio_path),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_sec),
            "-c",
            "copy",
            str(pattern),
        ],
    )
    return sorted(out_dir.glob("chunk_*.wav"))


def extract_scene_frames(ffmpeg_bin: str, video_path: Path, out_dir: Path, threshold: float) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "scene_%06d.png"
    run_ffmpeg(
        ffmpeg_bin,
        [
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"select=gt(scene\\,{threshold}),showinfo",
            "-vsync",
            "vfr",
            str(pattern),
        ],
    )
    return sorted(out_dir.glob("scene_*.png"))


def extract_fallback_frames(ffmpeg_bin: str, video_path: Path, out_dir: Path, interval_sec: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "fallback_%06d.png"
    run_ffmpeg(
        ffmpeg_bin,
        [
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{interval_sec}",
            str(pattern),
        ],
    )
    return sorted(out_dir.glob("fallback_*.png"))


def probe_duration(ffmpeg_bin: str, media_path: Path) -> float:
    ffprobe = ffmpeg_bin.replace("ffmpeg", "ffprobe")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(media_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return 0.0
    try:
        payload = json.loads(proc.stdout)
        return float(payload["format"]["duration"])
    except Exception:
        return 0.0
