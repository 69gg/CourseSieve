from __future__ import annotations

import json
import logging
from pathlib import Path
import sys

import typer
from rich import print

from coursesieve.config import RuntimeConfig
from coursesieve.pipeline.run import make_context, run_step
from coursesieve.pipeline.steps.asr import run_asr
from coursesieve.pipeline.steps.export import run_export
from coursesieve.pipeline.steps.fetch import run_fetch
from coursesieve.pipeline.steps.frames import run_frames
from coursesieve.pipeline.steps.fuse import run_fuse
from coursesieve.pipeline.steps.ocr import run_ocr
from coursesieve.pipeline.steps.prep import run_prep
from coursesieve.pipeline.steps.reduce import run_reduce
from coursesieve.pipeline.steps.summarize import run_summarize
from coursesieve.utils.deps import probe_dependencies
from coursesieve.utils.logging import setup_logging

app = typer.Typer(help="CourseSieve CLI")
logger = logging.getLogger(__name__)


def _config(
    source_input: str,
    out: Path,
    lang: str,
    ocr_lang: str,
    chunk_min: int,
    scene_threshold: float,
    frame_fallback_sec: int,
    asr_backend: str,
    asr_model: str,
    llm_provider: str | None,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    player: str,
    bili_cookie: str,
    bili_quality: int,
    bili_timeout: float,
    bili_overwrite: bool,
    download_dir: Path | None,
    ocr_window_delta_sec: float,
    ocr_change_insert_min: int,
    map_retry: int,
    max_workers: int,
) -> RuntimeConfig:
    return RuntimeConfig(
        source_input=source_input,
        out_dir=out.expanduser().resolve(),
        lang=lang,
        ocr_lang=ocr_lang,
        chunk_min=chunk_min,
        scene_threshold=scene_threshold,
        frame_fallback_sec=frame_fallback_sec,
        asr_backend=asr_backend,
        asr_model=asr_model,
        llm_provider=llm_provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        player=player,
        bili_cookie=bili_cookie,
        bili_quality=bili_quality,
        bili_timeout=bili_timeout,
        bili_overwrite=bili_overwrite,
        download_dir=download_dir.expanduser().resolve() if download_dir else None,
        ocr_window_delta_sec=ocr_window_delta_sec,
        ocr_change_insert_min=ocr_change_insert_min,
        map_retry=map_retry,
        max_workers=max_workers,
    )


def _run_pipeline(config: RuntimeConfig, target: str, enable_ocr: bool, debug: bool) -> dict[str, dict[str, str]]:
    setup_logging(debug=debug)
    logger.info(
        "Starting pipeline: target=%s input=%s out=%s ocr=%s debug=%s",
        target,
        config.source_input,
        config.out_dir,
        enable_ocr,
        debug,
    )
    ctx = make_context(config)
    vendor_root = _discover_vendor_root()
    if vendor_root:
        logger.info("Using vendor binaries from: %s", vendor_root)
    deps = probe_dependencies(
        enable_ocr=enable_ocr and target in {"ocr", "fuse", "summarize", "reduce", "export", "run"},
        vendor_root=vendor_root,
    )

    done: dict[str, dict[str, str]] = {}

    done["fetch"] = run_step(
        ctx,
        "fetch",
        {
            "source": config.source_input,
            "bili_quality": config.bili_quality,
            "bili_timeout": config.bili_timeout,
            "bili_overwrite": config.bili_overwrite,
            "download_dir": str(config.download_dir) if config.download_dir else None,
        },
        lambda: run_fetch(ctx),
    )
    if target == "fetch":
        return done

    done["prep"] = run_step(
        ctx,
        "prep",
        {"chunk_min": config.chunk_min, "ffmpeg": deps.ffmpeg},
        lambda: run_prep(ctx, ffmpeg_bin=deps.ffmpeg or "ffmpeg"),
    )
    if target == "prep":
        return done

    done["asr"] = run_step(
        ctx,
        "asr",
        {"asr_backend": config.asr_backend, "asr_model": config.asr_model, "lang": config.lang},
        lambda: run_asr(ctx),
    )
    if target == "asr":
        return done

    done["frames"] = run_step(
        ctx,
        "frames",
        {
            "scene_threshold": config.scene_threshold,
            "frame_fallback_sec": config.frame_fallback_sec,
            "ffmpeg": deps.ffmpeg,
        },
        lambda: run_frames(ctx, ffmpeg_bin=deps.ffmpeg or "ffmpeg"),
    )
    if target == "frames":
        return done

    if enable_ocr:
        done["ocr"] = run_step(
            ctx,
            "ocr",
            {"ocr_lang": config.ocr_lang, "tesseract": deps.tesseract},
            lambda: run_ocr(ctx, tesseract_cmd=deps.tesseract),
        )
    else:
        logger.warning("OCR disabled by flag, generating empty OCR output")
        done["ocr"] = {"ocr_jsonl": str(ctx.cache.ocr_dir / "ocr.jsonl")}
        Path(done["ocr"]["ocr_jsonl"]).write_text("", encoding="utf-8")
    if target == "ocr":
        return done

    done["fuse"] = run_step(
        ctx,
        "fuse",
        {
            "ocr_window_delta_sec": config.ocr_window_delta_sec,
            "ocr_change_insert_min": config.ocr_change_insert_min,
        },
        lambda: run_fuse(ctx),
    )
    if target == "fuse":
        return done

    done["summarize"] = run_step(
        ctx,
        "summarize",
        {
            "chunk_min": config.chunk_min,
            "llm_provider": config.llm_provider,
            "model": config.model,
            "base_url": config.base_url,
            "map_retry": config.map_retry,
        },
        lambda: run_summarize(ctx),
    )
    if target == "summarize":
        return done

    done["reduce"] = run_step(
        ctx,
        "reduce",
        {"player": config.player},
        lambda: run_reduce(ctx),
    )
    if target == "reduce":
        return done

    done["export"] = run_step(
        ctx,
        "export",
        {"player": config.player},
        lambda: run_export(ctx),
    )
    logger.info("Pipeline completed for target=%s", target)
    return done


def _discover_vendor_root() -> Path | None:
    candidates: list[Path] = [Path.cwd() / "vendor"]

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir / "vendor",
                exe_dir / "_internal" / "vendor",
            ]
        )
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "vendor")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    return None


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


@app.command()
def run(
    source_input: str = typer.Argument(..., help="本地视频路径或 B 站 BV/AV/URL/短链"),
    out: Path = typer.Option(Path("./out"), "--out"),
    lang: str = typer.Option("zh", "--lang"),
    ocr_lang: str = typer.Option("chi_sim+eng", "--ocr-lang"),
    chunk_min: int = typer.Option(12, "--chunk-min"),
    scene_threshold: float = typer.Option(0.35, "--scene-threshold"),
    frame_fallback_sec: int = typer.Option(30, "--frame-fallback-sec"),
    asr_backend: str = typer.Option("faster-whisper", "--asr-backend"),
    asr_model: str = typer.Option("medium", "--asr-model"),
    llm_provider: str | None = typer.Option(None, "--llm-provider"),
    base_url: str | None = typer.Option(None, "--base-url"),
    api_key: str | None = typer.Option(None, "--api-key"),
    model: str | None = typer.Option(None, "--model"),
    player: str = typer.Option("mpv", "--player"),
    bili_cookie: str = typer.Option("", "--bili-cookie"),
    bili_quality: int = typer.Option(80, "--bili-quality"),
    bili_timeout: float = typer.Option(30.0, "--bili-timeout"),
    bili_overwrite: bool = typer.Option(True, "--bili-overwrite/--no-bili-overwrite"),
    download_dir: Path | None = typer.Option(None, "--download-dir"),
    ocr_window_delta_sec: float = typer.Option(2.0, "--ocr-window-delta-sec"),
    ocr_change_insert_min: int = typer.Option(3, "--ocr-change-insert-min"),
    map_retry: int = typer.Option(2, "--map-retry"),
    max_workers: int = typer.Option(2, "--max-workers"),
    disable_ocr: bool = typer.Option(False, "--disable-ocr"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        lang,
        ocr_lang,
        chunk_min,
        scene_threshold,
        frame_fallback_sec,
        asr_backend,
        asr_model,
        llm_provider,
        base_url,
        api_key,
        model,
        player,
        bili_cookie,
        bili_quality,
        bili_timeout,
        bili_overwrite,
        download_dir,
        ocr_window_delta_sec,
        ocr_change_insert_min,
        map_retry,
        max_workers,
    )
    result = _run_pipeline(config, target="run", enable_ocr=not disable_ocr, debug=debug)
    _print_json(result)


@app.command()
def fetch(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    bili_cookie: str = typer.Option("", "--bili-cookie"),
    bili_quality: int = typer.Option(80, "--bili-quality"),
    bili_timeout: float = typer.Option(30.0, "--bili-timeout"),
    bili_overwrite: bool = typer.Option(True, "--bili-overwrite/--no-bili-overwrite"),
    download_dir: Path | None = typer.Option(None, "--download-dir"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        "chi_sim+eng",
        12,
        0.35,
        30,
        "faster-whisper",
        "medium",
        None,
        None,
        None,
        None,
        "mpv",
        bili_cookie,
        bili_quality,
        bili_timeout,
        bili_overwrite,
        download_dir,
        2.0,
        3,
        2,
        2,
    )
    result = _run_pipeline(config, target="fetch", enable_ocr=False, debug=debug)
    _print_json(result["fetch"])


@app.command()
def prep(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    chunk_min: int = typer.Option(12, "--chunk-min"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        "chi_sim+eng",
        chunk_min,
        0.35,
        30,
        "faster-whisper",
        "medium",
        None,
        None,
        None,
        None,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        2.0,
        3,
        2,
        2,
    )
    result = _run_pipeline(config, target="prep", enable_ocr=False, debug=debug)
    _print_json(result["prep"])


@app.command()
def asr(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    lang: str = typer.Option("zh", "--lang"),
    asr_model: str = typer.Option("medium", "--asr-model"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        lang,
        "chi_sim+eng",
        12,
        0.35,
        30,
        "faster-whisper",
        asr_model,
        None,
        None,
        None,
        None,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        2.0,
        3,
        2,
        2,
    )
    result = _run_pipeline(config, target="asr", enable_ocr=False, debug=debug)
    _print_json(result["asr"])


@app.command()
def frames(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    scene_threshold: float = typer.Option(0.35, "--scene-threshold"),
    frame_fallback_sec: int = typer.Option(30, "--frame-fallback-sec"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        "chi_sim+eng",
        12,
        scene_threshold,
        frame_fallback_sec,
        "faster-whisper",
        "medium",
        None,
        None,
        None,
        None,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        2.0,
        3,
        2,
        2,
    )
    result = _run_pipeline(config, target="frames", enable_ocr=False, debug=debug)
    _print_json(result["frames"])


@app.command()
def ocr(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    ocr_lang: str = typer.Option("chi_sim+eng", "--ocr-lang"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        ocr_lang,
        12,
        0.35,
        30,
        "faster-whisper",
        "medium",
        None,
        None,
        None,
        None,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        2.0,
        3,
        2,
        2,
    )
    result = _run_pipeline(config, target="ocr", enable_ocr=True, debug=debug)
    _print_json(result["ocr"])


@app.command()
def fuse(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    ocr_window_delta_sec: float = typer.Option(2.0, "--ocr-window-delta-sec"),
    ocr_change_insert_min: int = typer.Option(3, "--ocr-change-insert-min"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        "chi_sim+eng",
        12,
        0.35,
        30,
        "faster-whisper",
        "medium",
        None,
        None,
        None,
        None,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        ocr_window_delta_sec,
        ocr_change_insert_min,
        2,
        2,
    )
    result = _run_pipeline(config, target="fuse", enable_ocr=True, debug=debug)
    _print_json(result["fuse"])


@app.command()
def summarize(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    chunk_min: int = typer.Option(12, "--chunk-min"),
    llm_provider: str | None = typer.Option(None, "--llm-provider"),
    base_url: str | None = typer.Option(None, "--base-url"),
    api_key: str | None = typer.Option(None, "--api-key"),
    model: str | None = typer.Option(None, "--model"),
    map_retry: int = typer.Option(2, "--map-retry"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        "chi_sim+eng",
        chunk_min,
        0.35,
        30,
        "faster-whisper",
        "medium",
        llm_provider,
        base_url,
        api_key,
        model,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        2.0,
        3,
        map_retry,
        2,
    )
    result = _run_pipeline(config, target="summarize", enable_ocr=True, debug=debug)
    _print_json(result["summarize"])


@app.command()
def reduce(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        "chi_sim+eng",
        12,
        0.35,
        30,
        "faster-whisper",
        "medium",
        None,
        None,
        None,
        None,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        2.0,
        3,
        2,
        2,
    )
    result = _run_pipeline(config, target="reduce", enable_ocr=True, debug=debug)
    _print_json(result["reduce"])


@app.command()
def export(
    source_input: str,
    out: Path = typer.Option(Path("./out"), "--out"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    config = _config(
        source_input,
        out,
        "zh",
        "chi_sim+eng",
        12,
        0.35,
        30,
        "faster-whisper",
        "medium",
        None,
        None,
        None,
        None,
        "mpv",
        "",
        80,
        30.0,
        True,
        None,
        2.0,
        3,
        2,
        2,
    )
    result = _run_pipeline(config, target="export", enable_ocr=True, debug=debug)
    _print_json(result["export"])


if __name__ == "__main__":
    app()
