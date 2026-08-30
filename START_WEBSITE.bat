@echo off
cd /d "%~dp0"
echo.
echo   Starting your EGX Research website...
echo.
echo   When it says "Serving HTTP", open your browser to:
echo.
echo        http://127.0.0.1:8200
echo.
echo   To stop the website, close this window.
echo.
python -m http.server 8200 --directory site
pause
