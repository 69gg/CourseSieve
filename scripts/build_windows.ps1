Param(
  [string]$PythonVersion = "3.11",
  [string]$EntryScript = "coursesieve/cli.py",
  [string]$AppName = "coursesieve",
  [string]$UvCacheDir = ""
)

$ErrorActionPreference = "Stop"
if ($UvCacheDir -ne "") {
  $env:UV_CACHE_DIR = $UvCacheDir
}

Write-Host "[1/5] Checking uv..."
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv is required but was not found in PATH."
}

Write-Host "[2/5] Sync dependencies..."
uv sync

Write-Host "[3/5] Prepare pyinstaller args..."
$pyArgs = @(
  "--noconfirm"
  "--clean"
  "--onedir"
  "--name"
  $AppName
  "--collect-all"
  "coursesieve"
)

if (Test-Path "vendor") {
  # Keep vendor binaries beside exe (onedir) for ffmpeg/tesseract discovery.
  $pyArgs += "--add-data"
  $pyArgs += "vendor;vendor"
}
if (Test-Path "LICENSE") {
  # Include license file in onedir output.
  $pyArgs += "--add-data"
  $pyArgs += "LICENSE;."
}

Write-Host "[4/5] Build onedir exe..."
$pyArgs += $EntryScript
uv run --with pyinstaller pyinstaller @pyArgs

if (Test-Path "LICENSE") {
  Copy-Item "LICENSE" (Join-Path "dist/$AppName" "LICENSE") -Force
}

Write-Host "[5/5] Done. Output: dist/$AppName"
