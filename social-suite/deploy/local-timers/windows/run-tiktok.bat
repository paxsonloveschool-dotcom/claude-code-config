@echo off
REM Uploads the week's approved HP clips to TikTok's scheduler (song + Mon/Wed/Fri
REM slots). Called by the weekly Task Scheduler job, or run by hand.
REM The first ever run opens a browser to log in once (saves Tk_cookies_hp.json).
setlocal
call "%~dp0..\config.env.bat"
cd /d "%SOCIAL_SUITE_DIR%"
"%PYTHON%" automation\tiktok_browser_post.py --brand hp
