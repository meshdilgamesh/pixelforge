@echo off
rem ─────────────────────────────────────────────────────────────────────────
rem  PixelForge installer for Windows (native — no WSL needed)
rem  Installs to %LOCALAPPDATA%\PixelForge and creates a Start Menu shortcut.
rem  Run from the extracted release folder:  double-click install.bat
rem ─────────────────────────────────────────────────────────────────────────
setlocal
set "DEST=%LOCALAPPDATA%\PixelForge"
set "SRC=%~dp0"

echo Installing PixelForge to %DEST% ...
if not exist "%DEST%" mkdir "%DEST%"
rem copy code, keep user data on reinstalls
robocopy "%SRC%" "%DEST%" /E /NFL /NDL /NJH /NJS ^
  /XD .venv outputs uploads datasets __pycache__ .git dist >nul
if errorlevel 8 ( echo Copy failed & pause & exit /b 1 )

where uv >nul 2>nul
if errorlevel 1 (
  echo Setting up Python tooling - one time, no admin rights needed...
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)
set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV%" for /f "delims=" %%i in ('where uv 2^>nul') do set "UV=%%i"

if not exist "%DEST%\.venv\Scripts\python.exe" (
  echo Installing PyTorch + dependencies - one time, ~3 GB download...
  "%UV%" venv --python 3.13 "%DEST%\.venv"
  "%UV%" pip install -p "%DEST%\.venv\Scripts\python.exe" torch spandrel pillow numpy fastapi "uvicorn[standard]" python-multipart
)

rem app icon
"%DEST%\.venv\Scripts\python.exe" -c "from PIL import Image,ImageDraw; img=Image.new('RGBA',(128,128),(10,13,24,255)); d=ImageDraw.Draw(img); d.rounded_rectangle([10,10,58,58],radius=8,fill=(139,92,246,255)); d.rounded_rectangle([70,70,118,118],radius=8,fill=(34,211,238,255)); d.rectangle([60,60,68,68],fill=(244,114,182,255)); img.save(r'%DEST%\icon.png')" 2>nul

rem Start Menu shortcut
powershell -NoProfile -c ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:APPDATA+'\Microsoft\Windows\Start Menu\Programs\PixelForge.lnk'); $s.TargetPath='%DEST%\start.bat'; $s.WorkingDirectory='%DEST%'; $s.IconLocation='%DEST%\icon.png'; $s.Save()"

echo.
echo   PixelForge is installed.
echo     - Start Menu  -^> look for 'PixelForge'
echo     - First launch downloads the AI models - one time.
pause
