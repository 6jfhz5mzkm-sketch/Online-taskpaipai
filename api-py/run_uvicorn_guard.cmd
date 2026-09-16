@echo off
REM 商家任务体系 Python 后端 uvicorn 守护脚本(防进程挂掉)
setlocal
set BASE=D:\ext.ahs.luoyingkai1\Desktop\CodeX\Task Framework\api-py
set PY=%BASE%\.venv\Scripts\python.exe
set PORT=8000
:loop
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
  timeout /t 10 /nobreak >nul 2>&1
) else (
  cd /d "%BASE%"
  start "" "%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
  timeout /t 5 /nobreak >nul 2>&1
)
goto loop
