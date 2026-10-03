@echo off
rem ============================================================
rem  PixelForge installer for Windows (simple console version)
rem  Tip: for a setup window with an install-location picker,
rem  run setup.bat instead.
rem ============================================================
setlocal enabledelayedexpansion
title PixelForge Setup
set "SRC=%~dp0"
set "DEST=%LOCALAPPDATA%\PixelForge"

rem a trailing backslash would escape the closing quote in quoted paths
if "!SRC:~-1!"=="\" set "SRC=!SRC:~0,-1!"

rem ---- pre-flight checks ------------------------------------------------
if not exist "!SRC!\pixelforge.py" (
  echo.
  echo  ERROR: pixelforge.py not found next to this installer.
  echo  Windows can run .bat files straight from inside a zip, but that
  echo  breaks installation. Please EXTRACT the zip first ^(right-click ^
  echo  ^> Extract All^), then open the extracted folder and run install.bat.
  echo.
  pause
  exit /b 1
)

echo.
echo  Installing PixelForge to:  !DEST!
echo.
if not exist "!DEST!" mkdir "!DEST!"

rem copy everything including a prepared .venv (if start.bat already ran here),
rem so the ~3 GB PyTorch download is not repeated
robocopy "!SRC!" "!DEST!" /E /NFL /NDL /NJH /NJS /XD outputs uploads datasets __pycache__ .git dist
set "RC=!errorlevel!"
if !RC! GEQ 8 (
  echo.
  echo  Copy failed - robocopy exit code !RC!.
  echo  Common causes:
  echo    - antivirus blocked the copy ^(check your AV notifications^)
  echo    - OneDrive/permissions blocking !DEST!
  echo  You can also skip installing and just run start.bat from this folder.
  echo.
  pause
  exit /b 1
)

cd /d "!DEST!"

rem ---- python + CUDA torch ------------------------------------------------
where uv >nul 2>nul
if errorlevel 1 (
  echo  Setting up Python tooling - one time, no admin rights needed...
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "!UV!" for /f "delims=" %%i in ('where uv 2^>nul') do set "UV=%%i"
if not defined UV (
  echo  Could not find or install uv. Install it from https://docs.astral.sh/uv/
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  Creating Python environment - one time...
  "!UV!" venv --python 3.13 .venv
)
".venv\Scripts\python.exe" -c "import torch" >nul 2>nul
if errorlevel 1 (
  echo  Installing PyTorch with NVIDIA CUDA support - one time, ~3 GB download...
  "!UV!" pip install -p .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu126
)
where nvidia-smi >nul 2>nul
if not errorlevel 1 (
  ".venv\Scripts\python.exe" -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>nul
  if errorlevel 1 (
    echo  Upgrading PyTorch to the NVIDIA CUDA build - one time, ~3 GB...
    "!UV!" pip install -p .venv\Scripts\python.exe --reinstall-package torch --index-url https://download.pytorch.org/whl/cu126
  )
)
".venv\Scripts\python.exe" -c "import spandrel, fastapi" >nul 2>nul
if errorlevel 1 (
  echo  Installing app dependencies - one time...
  "!UV!" pip install -p .venv\Scripts\python.exe spandrel pillow numpy fastapi "uvicorn[standard]" python-multipart
)

rem ---- Start Menu shortcut ------------------------------------------------
powershell -NoProfile -c ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:APPDATA+'\Microsoft\Windows\Start Menu\Programs\PixelForge.lnk'); $s.TargetPath='!DEST!\start.bat'; $s.WorkingDirectory='!DEST!'; $s.Save()" >nul 2>nul

echo.
echo  =====================================================
echo   PixelForge is installed!
echo     - Start Menu  : look for 'PixelForge'
echo     - Run now     : double-click start.bat in !DEST!
echo     - First launch downloads the AI models (one time)
echo  =====================================================
pause
