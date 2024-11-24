@echo off
REM Using start command to run programs asynchronously
REM /D sets starting directory, /MIN minimizes window if desired

start "" /D "%~dp0" cmd /c "python kiosk/kiosk.py"
REM Launch admin program on left monitor (primary - 1920,0 assumes 1920x1080 resolution)
start "" /D "%~dp0" cmd /c "python admin/admin_main.py"

REM Launch kiosk program

REM Alternative version using absolute positioning for first window
REM Requires NirCmd utility: https://www.nirsoft.net/utils/nircmd.html
REM start "" /D "%~dp0" cmd /c "nircmd win setpos title "Python" 0 0 960 1080 && python admin/admin_main.py"