@echo off
setlocal
cd /d "%~dp0.."
call "%~dp0_find_python.bat" || exit /b 1
"%PY%" scripts\run_api.py %*
exit /b %ERRORLEVEL%
