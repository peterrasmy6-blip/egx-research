@echo off
cd /d "%~dp0"
echo.
echo   Rebuilding the website from the latest data in the database...
echo   (This does not download new prices - ask Claude to "update the market data" for that.)
echo.
python backend\export_static.py
echo.
echo   Done. The updated website is in the "site" folder.
echo.
pause
