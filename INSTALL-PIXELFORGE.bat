@echo off
rem PixelForge Setup - launches the graphical wizard.
rem The PowerShell window is hidden; only the setup GUI is shown.
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0setup-engine.ps1"
exit
