@echo off
setlocal
cd /d "%~dp0.."
call "%~dp0_find_python.bat" || exit /b 1
"%PY%" scripts\run_ui.py %*
exit /b %ERRORLEVEL%
