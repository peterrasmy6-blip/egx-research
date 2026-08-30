@echo off
cd /d "%~dp0"
echo.
echo ============================================================
echo   1 of 3  -  Python engine tests
echo ============================================================
python backend\tests\test_engine.py
python backend\tests\test_engines2.py
echo.
echo ============================================================
echo   2 of 3  -  Rebuilding browser parity fixtures
echo ============================================================
python backend\tests\build_parity_cases.py
echo.
echo ============================================================
echo   3 of 3  -  Browser parity test
echo ============================================================
echo.
echo   Starting a test server. When it is running, open:
echo.
echo        http://127.0.0.1:8300/tests/parity_harness.html
echo.
echo   Green = the browser maths matches the Python maths.
echo   Close this window when finished.
echo.
python -m http.server 8300 --directory backend
pause
