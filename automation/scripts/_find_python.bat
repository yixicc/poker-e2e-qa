@echo off
REM 输出：设置环境变量 PY
set "PY="
if exist "%~dp0..\.venv\Scripts\python.exe" (
  set "PY=%~dp0..\.venv\Scripts\python.exe"
  goto :eof
)
where py >nul 2>&1 && (
  for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%i"
)
if defined PY goto :eof
where python >nul 2>&1 && set "PY=python"
if defined PY goto :eof
echo 找不到 Python。请先在 automation 目录执行:
echo   py -3 -m venv .venv
echo   .venv\Scripts\pip install -r requirements.txt
exit /b 1
