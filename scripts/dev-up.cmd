@echo off
setlocal EnableExtensions
rem ============================================================
rem dev-up.cmd  -  start ONLY the local dev services that are currently DOWN
rem   ports: 8000 (api-py/uvicorn, NO --reload), 5173 (H5 uni dev), 5174 (admin vite)
rem   flow : probe -> start the missing ones -> wait 35s -> probe again (dev-status.cmd)
rem   wait : powershell Start-Sleep (not "timeout", which aborts when stdin is redirected)
rem   start: detached via WMI Win32_Process Create (survives this console), absolute paths only
rem   logs : %TEMP%\dev-api-py.{out,err}.log , %TEMP%\dev-h5.{out,err}.log , %TEMP%\dev-admin.{out,err}.log  (append)
rem   exit code: 0 = all three UP and 200 after the wait ; 1 = otherwise
rem   one-shot helper: NO watchdog / NO auto-restart / NO scheduled task (by design)
rem   usage: "%ROOT%\scripts\dev-up.cmd"   (run from any cwd)
rem ============================================================
set "ROOT=%~dp0.."
set "STARTED=0"

call :check_down 8000
if not errorlevel 1 call :start_api && set "STARTED=1"
call :check_down 5173
if not errorlevel 1 call :start_h5 && set "STARTED=1"
call :check_down 5174
if not errorlevel 1 call :start_admin && set "STARTED=1"

if "%STARTED%"=="0" (
  echo RESULT: NOTHING_TO_START ^(all three ports already UP^)
) else (
  echo WAITING 35s for freshly started services ...
  powershell -NoProfile -Command "Start-Sleep -Seconds 35"
)
call "%ROOT%\scripts\dev-status.cmd"
exit /b %ERRORLEVEL%

:check_down
rem errorlevel 0 = port is DOWN (needs start) ; 1 = port is UP (skip)
set "PF="
for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr /c:":%~1 "') do set "PF=%%A"
if defined PF (
  echo SKIP %~1 already UP pid=%PF%
  exit /b 1
)
echo NEED %~1 is DOWN
exit /b 0

:start_api
set "DEV_CWD=%ROOT%\api-py"
set "DEV_CMD=cmd.exe /c cd /d "%ROOT%\api-py" && ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 1>>"%TEMP%\dev-api-py.out.log" 2>>"%TEMP%\dev-api-py.err.log""
call :spawn api-py
exit /b 0

:start_h5
set "DEV_CWD=%ROOT%\project"
set "DEV_CMD=cmd.exe /c node "%ROOT%\project\node_modules\@dcloudio\vite-plugin-uni\bin\uni.js" -p h5 1>>"%TEMP%\dev-h5.out.log" 2>>"%TEMP%\dev-h5.err.log""
call :spawn h5
exit /b 0

:start_admin
set "DEV_CWD=%ROOT%\admin"
set "DEV_CMD=cmd.exe /c node "%ROOT%\admin\node_modules\vite\bin\vite.js" 1>>"%TEMP%\dev-admin.out.log" 2>>"%TEMP%\dev-admin.err.log""
call :spawn admin
exit /b 0

:spawn
for /f "usebackq delims=" %%R in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$env:DEV_CMD; CurrentDirectory=$env:DEV_CWD}; Write-Output ('WMI=' + $r.ReturnValue + ' cmd_pid=' + $r.ProcessId)"`) do echo SPAWN %~1 %%R
goto :eof
