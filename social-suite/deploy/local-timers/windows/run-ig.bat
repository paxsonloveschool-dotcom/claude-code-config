@echo off
REM Posts ONE new HP clip to Instagram as a Reel with the next chosen song.
REM Called by the Task Scheduler job (Mon/Wed/Fri 11:00), or run by hand.
setlocal
call "%~dp0..\config.env.bat"
set "IG_FOLDER=%IG_FOLDER%"
set "IG_CREDS=%IG_CREDS%"
cd /d "%SOCIAL_SUITE_DIR%"
"%PYTHON%" automation\ig_autopost.py
