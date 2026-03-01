from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def run_ffmpeg(ffmpeg_bin: str, args: list[str]) -> None:
    cmd = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", *args]
    logger.debug("Running ffmpeg command: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()}")


def extract_audio(ffmpeg_bin: str, video_path: Path, audio_path: Path) -> None:
    logger.info("Extracting audio: %s -> %s", video_path, audio_path)
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
    logger.info("Splitting audio into %ss chunks: %s", chunk_sec, audio_path)
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
    chunks = sorted(out_dir.glob("chunk_*.wav"))
    logger.info("Generated %d audio chunks in %s", len(chunks), out_dir)
    return chunks


def extract_scene_frames(ffmpeg_bin: str, video_path: Path, out_dir: Path, threshold: float) -> list[Path]:
    logger.info("Extracting scene frames (threshold=%s) from %s", threshold, video_path)
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
    frames = sorted(out_dir.glob("scene_*.png"))
    logger.info("Generated %d scene frames in %s", len(frames), out_dir)
    return frames


def extract_fallback_frames(ffmpeg_bin: str, video_path: Path, out_dir: Path, interval_sec: int) -> list[Path]:
    logger.info("Extracting fallback frames every %ss from %s", interval_sec, video_path)
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
    frames = sorted(out_dir.glob("fallback_*.png"))
    logger.info("Generated %d fallback frames in %s", len(frames), out_dir)
    return frames


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
    logger.debug("Probing media duration with %s: %s", ffprobe, media_path)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.warning("Failed to probe duration for %s: %s", media_path, proc.stderr.strip())
        return 0.0
    try:
        payload = json.loads(proc.stdout)
        duration = float(payload["format"]["duration"])
        logger.debug("Media duration: %.2fs (%s)", duration, media_path)
        return duration
    except Exception:
        logger.warning("Failed to parse duration output for %s", media_path)
        return 0.0
