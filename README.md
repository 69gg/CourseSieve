# CourseSieve（课筛）

把「本地视频 / 哔哩哔哩视频」自动变成“可跳转回看”的复习要点与考点笔记。

- 形态：CLI 工具（Python 3.11+）
- 依赖管理：`uv`
- 核心能力：下载（可选）/ ASR / 关键帧 OCR / 融合 / Map-Reduce 总结 / 索引导出
- 设计原则：所有结论带时间锚点，可回看核验

## 1. 功能概览

输入：
- 本地文件路径（如 `./lecture.mp4`）
- B 站 BV/AV/URL/b23 短链（自动调用 `oh-my-bilibili`）

输出（关键文件）：
- `asr/transcript.srt`
- `fused/fused.md`
- `final/notes.md`
- `final/review_checklist.md`
- `final/exam_points.md`
- `final/index.md`
- `final/chapters.ffmetadata`

## 2. 项目结构

```text
coursesieve/
  cli.py
  config.py
  sources/
  pipeline/
    run.py
    steps/
  media/
  asr/
  ocr/
  llm/
  store/
  utils/
scripts/
  build_windows.ps1
  build_windows.bat
tests/
pyproject.toml
README.md
```

## 3. 环境要求

- Python `>=3.11`
- 系统依赖：
1. `ffmpeg`（必需）
2. `tesseract`（启用 OCR 时必需）
3. `mpv`（可选，用于直接命令跳转）

Windows 推荐目录（可选）：
- `vendor/ffmpeg/ffmpeg.exe`
- `vendor/tesseract/tesseract.exe`

程序会优先使用 `vendor`，找不到再走 `PATH`。

## 4. 安装与开发

### 4.1 克隆后初始化

```bash
uv sync
```

### 4.2 运行 CLI

```bash
uv run coursesieve --help
```

## 5. 一条命令跑通

```bash
uv run coursesieve run "https://www.bilibili.com/video/BVxxxx" \
  --bili-cookie "SESSDATA=..." \
  --out "./out" \
  --lang zh \
  --ocr-lang "chi_sim+eng" \
  --chunk-min 12 \
  --scene-threshold 0.35 \
  --frame-fallback-sec 30 \
  --asr-backend faster-whisper --asr-model medium \
  --llm-provider openai_compat --base-url "http://localhost:8000/v1" --api-key "sk-xxx" --model "gpt-4o-mini" \
  --player mpv
```

如果机器未安装 tesseract 且你暂时只想跑 ASR：

```bash
uv run coursesieve run ./lecture.mp4 --disable-ocr
```

## 6. 子命令（调试友好）

```bash
uv run coursesieve fetch <input>
uv run coursesieve prep <input>
uv run coursesieve asr <input>
uv run coursesieve frames <input>
uv run coursesieve ocr <input>
uv run coursesieve fuse <input>
uv run coursesieve summarize <input>
uv run coursesieve reduce <input>
uv run coursesieve export <input>
```

说明：每个子命令会自动补齐必要前置步骤，并复用缓存。

## 7. 断点续跑与缓存

工作目录：

```text
<out>/.cache/<video_id>/
```

其中 `<video_id>` 由：
- `source_input`
- 影响语义结果的关键参数（ASR/OCR/LLM 相关）

每个 step 产物落盘并记录到 `manifest.json`：
- `done`
- `params_hash`
- `outputs`
- `duration_sec`
- `updated_at`

重跑时，如果参数哈希一致则跳过该步骤。

## 8. 主要参数

- 输入与下载：
1. `--bili-cookie`
2. `--bili-quality`（默认 80）
3. `--bili-timeout`（默认 30）
4. `--bili-overwrite / --no-bili-overwrite`
5. `--download-dir`

- 视觉补全：
1. `--scene-threshold`（默认 0.35）
2. `--frame-fallback-sec`（默认 30）
3. `--ocr-lang`（默认 `chi_sim+eng`）

- 转录与总结：
1. `--asr-model`（默认 `medium`）
2. `--chunk-min`（默认 12）
3. `--llm-provider openai_compat`
4. `--base-url` / `--api-key` / `--model`
5. `--map-retry`（默认 2）

## 9. 输出说明

### 9.1 `fused/fused.md`
融合后的可读语料，格式示例：

```text
[00:12:01 - 00:12:19] 口播文本...
[SCREEN @ 00:12:01] PPT/OCR 文本...
```

### 9.2 `final/index.md`
每条记录包含时间点与跳转命令：

```bash
mpv "<video_path>" --start=HH:MM:SS
```

### 9.3 `final/chapters.ffmetadata`
标准 FFMETADATA 章节文件，可供后续封装章节。

## 10. 与 oh-my-bilibili 集成

已按以下行为接入：
- 自动识别 BV/AV/URL/b23 输入
- 调用 `oh_my_bilibili.fetch(...)`
- 支持 `cookie / prefer_quality / timeout / overwrite`
- 下载结果作为后续统一本地输入

## 11. LLM 策略

Map 阶段默认强制 JSON schema 校验：
- 校验成功：写入 `map/chunk_XXX.json`
- 校验失败：按 `--map-retry` 重试
- 仍失败：退化为 heuristic 总结并写入 `uncertain`

如果未配置 LLM，系统会自动走 heuristic 模式，保证流程可完成。

## 12. 质量建议

- 中文课程：建议 `--ocr-lang chi_sim+eng`
- 板书多、翻页少：降低 `--frame-fallback-sec`（如 15-20）
- PPT切换频繁：提高 `--scene-threshold` 到 `0.4~0.5`
- 长视频：保持 `--chunk-min 10~15`

## 13. Windows 打包（PyInstaller onedir）

### 13.1 直接脚本

PowerShell：

```powershell
./scripts/build_windows.ps1
```

或 CMD：

```bat
scripts\build_windows.bat
```

### 13.2 脚本行为

- 检查 `uv`
- 安装/同步依赖
- 使用 `uv run --with pyinstaller` 临时拉起打包器
- 生成 onedir 到 `dist/coursesieve/`
- 尝试打包 `vendor/`（若目录存在）

### 13.3 可执行产物

- `dist/coursesieve/coursesieve.exe`

运行示例：

```bat
dist\coursesieve\coursesieve.exe run "BVxxxx" --out .\out --disable-ocr
```

## 14. 本地构建包（sdist + wheel）

```bash
uv build
```

## 15. 常见问题

1. 报错 `ffmpeg not found`
- 安装 ffmpeg，或放到 `vendor/ffmpeg/ffmpeg.exe`。

2. 报错 `tesseract not found`
- 安装 tesseract 并确保 PATH 可见，或放到 `vendor/tesseract/tesseract.exe`。

3. B 站下载失败
- 检查 `SESSDATA` 是否有效。
- 会员/高清可能必须 cookie。

4. LLM JSON 解析失败
- 降低温度或换模型。
- 增加 `--map-retry`。
- 未配置 LLM 时可先跑 heuristic 验证流程。

## 16. 许可证

MIT
