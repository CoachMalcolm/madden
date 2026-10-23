@echo off
rem Madden Roster Kit: double-click, then paste your Google Sheets link or drag in your workbook / CSV files.
rem (Needs Python 3. The Windows program MaddenRosterKit.exe does the same without Python.)
cd /d "%~dp0"
set MADDEN_PAUSE=1
python madden_kit.py %*
