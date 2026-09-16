@echo off
setlocal EnableExtensions
rem ============================================================
rem dev-status.cmd  -  READ-ONLY health probe for the local dev stack
rem   ports: 8000 (api-py/uvicorn), 5173 (H5 uni dev server), 5174 (admin vite)
rem   output: PORT <port> UP pid=<pid> start=<yyyy-MM-dd HH:mm:ss>
rem           PORT <port> DOWN
rem           HTTP <url> -> <code>
rem   exit code:
rem     0 = all three ports UP  AND  all three HTTP probes return 200
rem     1 = otherwise (some port down, or some probe not 200)
rem   notes: 5174 binds ::1 only -> always probed via http://localhost:5174/
rem          run from any cwd: repo root = %~dp0..   (this file lives in <repo>\scripts\)
rem   no watchdog / no restart: this script only observes.
rem ============================================================
set "ROOT=%~dp0.."
set "FAIL=0"

for %%P in (8000 5173 5174) do call :probe_port %%P
call :probe_http "http://127.0.0.1:8000/health"
call :probe_http "http://127.0.0.1:5173/"
call :probe_http "http://localhost:5174/"

if "%FAIL%"=="0" (echo RESULT: ALL_UP_AND_200) else (echo RESULT: DEGRADED)
exit /b %FAIL%

:probe_port
set "PF="
for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr /c:":%~1 "') do set "PF=%%A"
if not defined PF (
  echo PORT %~1 DOWN
  set "FAIL=1"
  goto :eof
)
set "PSTART=unknown"
for /f "usebackq delims=" %%S in (`powershell -NoProfile -Command "(Get-Process -Id %PF% -ErrorAction SilentlyContinue).StartTime.ToString('yyyy-MM-dd HH:mm:ss')"`) do set "PSTART=%%S"
echo PORT %~1 UP pid=%PF% start=%PSTART%
goto :eof

:probe_http
set "CODE=000"
for /f "usebackq delims=" %%C in (`curl.exe -s -o NUL -w "%%{http_code}" --max-time 10 %~1`) do set "CODE=%%C"
echo HTTP %~1 -^> %CODE%
if not "%CODE%"=="200" set "FAIL=1"
goto :eof
