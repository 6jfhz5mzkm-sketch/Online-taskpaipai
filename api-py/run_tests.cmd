@echo off
rem ===================================================================
rem Backend full test entry (single command). Run from project root:
rem     npm run test:api
rem Targeted run (args REPLACE the default target "tests"):
rem     npm run test:api -- tests/test_fee_detail_contract.py -q
rem Notes:
rem   1) Prefer the api-py venv interpreter; fall back to "uv run".
rem   2) UV_CACHE_DIR points inside the repo so uv can start even when
rem      the default uv cache directory is not writable.
rem   3) -p no:cacheprovider keeps output clean on read-only checkouts
rem      (cost: --lf/--ff are unavailable).
rem   4) Exit code is propagated: 0 = all passed, 1 = at least one failed.
rem ===================================================================
setlocal
set "ROOT=%~dp0"
set "UV_CACHE_DIR=%ROOT%..\.uv-cache"
cd /d "%ROOT%"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY="

if "%~1"=="" (
  if defined PY (
    "%PY%" -m pytest tests -q -p no:cacheprovider
  ) else (
    uv run python -m pytest tests -q -p no:cacheprovider
  )
) else (
  if defined PY (
    "%PY%" -m pytest %* -p no:cacheprovider
  ) else (
    uv run python -m pytest %* -p no:cacheprovider
  )
)
exit /b %ERRORLEVEL%
