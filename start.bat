@echo off
rem ─────────────────────────────────────────────────────────────────────────
rem  PixelForge launcher for Windows
rem    start.bat            → web UI (opens your browser)
rem    start.bat photo.jpg  → CLI upscaling
rem  Requires an NVIDIA GPU + driver. First run installs everything (~3 GB).
rem ─────────────────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo Setting up Python tooling - one time, no admin rights needed...
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)
for /f "delims=" %%i in ('where uv 2^>nul') do set "UV=%%i"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV (
  echo Could not find or install uv. Install it from https://docs.astral.sh/uv/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment and installing PyTorch - one time, ~3 GB download...
  "%UV%" venv --python 3.13 .venv
  "%UV%" pip install -p .venv\Scripts\python.exe torch spandrel pillow numpy fastapi "uvicorn[standard]" python-multipart
)

".venv\Scripts\python.exe" pixelforge.py %*
pause
