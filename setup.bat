@echo off
rem PixelForge Setup — opens the graphical installer window.
rem (setup.ps1 does all the work; this file just launches it.)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 pause
