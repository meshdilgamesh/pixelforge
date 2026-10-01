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
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" for /f "delims=" %%i in ('where uv 2^>nul') do set "UV=%%i"
if not defined UV (
  echo Could not find or install uv. Install it from https://docs.astral.sh/uv/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment - one time...
  "%UV%" venv --python 3.13 .venv
)

rem NVIDIA CUDA build of PyTorch (the plain PyPI torch on Windows is CPU-only!)
".venv\Scripts\python.exe" -c "import torch" >nul 2>nul
if errorlevel 1 (
  echo Installing PyTorch with NVIDIA CUDA support - one time, ~3 GB download...
  "%UV%" pip install -p .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu126
)
where nvidia-smi >nul 2>nul
if not errorlevel 1 (
  ".venv\Scripts\python.exe" -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>nul
  if errorlevel 1 (
    echo Upgrading PyTorch to the NVIDIA CUDA build - one time, ~3 GB...
    "%UV%" pip install -p .venv\Scripts\python.exe --reinstall-package torch --index-url https://download.pytorch.org/whl/cu126
  )
)

".venv\Scripts\python.exe" -c "import spandrel, fastapi" >nul 2>nul
if errorlevel 1 (
  echo Installing app dependencies - one time...
  "%UV%" pip install -p .venv\Scripts\python.exe spandrel pillow numpy fastapi "uvicorn[standard]" python-multipart
)

".venv\Scripts\python.exe" pixelforge.py %*
pause
