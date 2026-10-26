@echo off
setlocal
cd /d "%~dp0.."
call "%~dp0_find_python.bat" || exit /b 1
"%PY%" scripts\gen_allure.py %*
exit /b %ERRORLEVEL%
