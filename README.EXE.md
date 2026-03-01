# CourseSieve 使用说明

## 1. 解压后你会看到

请把压缩包解压到任意目录，例如 `D:\CourseSieve\`。

常见文件：
- `coursesieve.exe`
- `README.md`（本文件）
- `LICENSE`
- `_internal\`（运行时文件）
- `vendor\`（可选，便携依赖）

`vendor` 里建议包含：
- `vendor\ffmpeg\ffmpeg.exe`
- `vendor\tesseract\tesseract.exe`
- `vendor\mpv\mpv.exe`

程序会优先使用 `vendor`，找不到再走系统 PATH。

## 2. 快速开始

在解压目录中打开 `cmd` 或 PowerShell，运行：

```bat
coursesieve.exe --help
```

全流程示例：

```bat
coursesieve.exe run "https://www.bilibili.com/video/BVxxxx" ^
  --bili-cookie "SESSDATA=..." ^
  --out ".\\out" ^
  --lang zh ^
  --ocr-lang "chi_sim+eng" ^
  --asr-model medium ^
  --llm-provider openai_compat --base-url "http://127.0.0.1:8000/v1" --api-key "sk-xxx" --model "your-model"
```

## 3. 结果在哪里看

推荐先看最新结果指针：

```bat
type out\results\LATEST.txt
```

然后进入该目录查看：
- `final\notes.md`
- `final\index.md`
- `final\exam_points.md`
- `final\chapters.ffmetadata`
- `artifacts\transcript.srt`
- `artifacts\fused.md`

## 4. 常见问题

`ffmpeg not found`：
- 把 `ffmpeg.exe` 放到 `vendor\ffmpeg\`，或安装到系统 PATH。

`tesseract not found`：
- 把 `tesseract.exe` 和 `tessdata` 放到 `vendor\tesseract\`，或安装到系统 PATH。

没有 `mpv`：
- 不影响主流程，只影响 `index.md` 里一键跳转命令的直接可用性。

## 5. 日常更新

如果只替换 `vendor` 里的二进制，不需要重新打包。
替换后可直接重新运行 `coursesieve.exe`。

## 6. 常用命令模板

本地视频（推荐先跑通）：

```bat
coursesieve.exe run "D:\video\lesson.mp4" ^
  --out ".\out" ^
  --asr-model small ^
  --disable-ocr
```

B 站视频（会自动下载）：

```bat
coursesieve.exe run "https://www.bilibili.com/video/BVxxxx" ^
  --bili-cookie "SESSDATA=..." ^
  --out ".\out" ^
  --asr-model small
```

仅下载：

```bat
coursesieve.exe fetch "BVxxxx" --bili-cookie "SESSDATA=..." --out ".\out"
```

仅做转录：

```bat
coursesieve.exe asr "D:\video\lesson.mp4" --out ".\out" --lang zh --asr-model small
```

仅做总结（前置步骤会自动补齐）：

```bat
coursesieve.exe summarize "D:\video\lesson.mp4" ^
  --out ".\out" ^
  --llm-provider openai_compat --base-url "http://127.0.0.1:8000/v1" --api-key "sk-xxx" --model "your-model"
```

## 7. 参数说明（`run` 命令）

输入与下载：
- `--bili-cookie`：B 站下载 cookie，会员/高清常常必需。
- `--bili-quality`：下载清晰度偏好，默认 `80`。
- `--bili-timeout`：下载请求超时秒数，默认 `30`。
- `--bili-overwrite / --no-bili-overwrite`：是否覆盖已下载文件。
- `--download-dir`：下载目录覆盖默认缓存路径。

ASR（语音转文本）：
- `--lang`：转录语言，中文常用 `zh`。
- `--asr-backend`：当前默认 `faster-whisper`。
- `--asr-model`：`small` 更快，`medium` 质量更高。
- `--chunk-min`：音频切块分钟数，默认 `12`。

抽帧与 OCR：
- `--scene-threshold`：场景变化阈值，默认 `0.35`。
- `--frame-fallback-sec`：兜底抽帧间隔秒，默认 `30`。
- `--ocr-lang`：OCR 语言，默认 `chi_sim+eng`。
- `--ocr-window-delta-sec`：ASR/OCR 对齐窗口，默认 `2.0` 秒。
- `--ocr-change-insert-min`：同屏内容最小插入间隔（分钟），默认 `3`。
- `--disable-ocr`：关闭 OCR（速度更快，信息更少）。

LLM 总结：
- `--llm-provider`：目前用 `openai_compat`。
- `--base-url`：OpenAI 兼容接口地址。
- `--api-key`：接口密钥。
- `--model`：模型名。
- `--map-retry`：单块总结失败重试次数，默认 `2`。

输出与调试：
- `--out`：输出根目录，默认 `.\out`。
- `--player`：索引里生成的播放器命令，默认 `mpv`。
- `--debug`：输出更详细日志（排错建议开启）。
- `--max-workers`：并发预留参数（当前版本保留位）。

## 8. 三档配置建议

快速档（先跑通）：
- `--asr-model small --disable-ocr`

平衡档（推荐日常）：
- `--asr-model small --ocr-lang "chi_sim+eng"`
- `--scene-threshold 0.35 --frame-fallback-sec 30`

高质量档（耗时更长）：
- `--asr-model medium --ocr-lang "chi_sim+eng"`
- `--frame-fallback-sec 15`
- 配置稳定 LLM（`--llm-provider` / `--base-url` / `--model`）

## 9. 故障排查

流程全是 `skip`：
- 说明命中缓存；删除 `out\.cache\` 后重跑。

LLM 返回空或字段不匹配：
- 加 `--debug`，查看 `out\.cache\<video_id>\map\debug\`。
- 确认你的网关支持 OpenAI tool-calls。

OCR 中文效果差：
- 检查 `vendor\tesseract\tessdata\chi_sim.traineddata` 是否存在。
- 把 `--ocr-lang` 保持为 `chi_sim+eng`。

找不到结果：
- 先执行 `type out\results\LATEST.txt` 获取最新目录。
- 再进入该目录查看 `final\notes.md` 和 `final\index.md`。
