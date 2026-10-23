@echo off
rem Drag your workbook (.xlsx, v6) or players file (.csv, old v5 sheet) onto this file,
rem or double-click and type the path. Either one works.
cd /d "%~dp0"
set "SRC=%~1"
if "%SRC%"=="" set /p "SRC=Workbook .xlsx or players .csv (drag the file into this window and press Enter): "
set "SRC=%SRC:"=%"
set /p "NAME=Roster name, letters and numbers only, 8 or fewer (e.g. GPSQUAD1): "
set "NAME=%NAME: =%"
if /i "%SRC:~-5%"==".xlsx" (
  python madden_build_v6.py "%SRC%" "%NAME%"
) else (
  set "TEAMS="
  if exist "input\teams.csv" set TEAMS=--teams "input\teams.csv"
  python madden_build.py "%SRC%" "%NAME%" %TEAMS%
)
echo.
if errorlevel 1 (
  echo Nothing was built. Read the messages above, fix them, and run it again.
) else (
  echo Done. The roster and report are in the output folder. The roster was also copied to
  echo Documents\Madden NFL 08\Rosters if that folder was found ^(see the COPIED line above^).
)
pause
