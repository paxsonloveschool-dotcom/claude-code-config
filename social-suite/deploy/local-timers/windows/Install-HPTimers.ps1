# Installs the HP local posting timers on Windows (Task Scheduler) with
# "wake the computer to run this task" enabled, so the PC can sleep the rest of
# the time.
#
#   Instagram : Mon/Wed/Fri 11:00  (posts one Reel per run — instant, no scheduler)
#   TikTok    : Mon 10:30 weekly    (uploads the week's batch to TikTok's scheduler)
#
# Run in PowerShell (normal user is fine; it registers per-user tasks):
#   powershell -ExecutionPolicy Bypass -File .\Install-HPTimers.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# config.env.bat lives one level up (shared) — fall back to the windows copy.
$cfg = Join-Path (Split-Path -Parent $here) "config.env.bat"
if (-not (Test-Path $cfg)) { $cfg = Join-Path $here "config.env.bat" }
if (-not (Test-Path $cfg)) {
  Write-Error "config.env.bat not found. Copy config.env.bat.example to config.env.bat and edit it, then move it up to the local-timers folder."
}

$igBat = Join-Path $here "run-ig.bat"
$ttBat = Join-Path $here "run-tiktok.bat"
foreach ($b in @($igBat, $ttBat)) { if (-not (Test-Path $b)) { Write-Error "Missing $b" } }

function Register-HPTask($name, $bat, $trigger) {
  $action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$bat`""
  $settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
    -Settings $settings -Description "HP auto-post ($name)" | Out-Null
  Write-Host "  registered $name"
}

Write-Host "Installing Task Scheduler jobs (WakeToRun enabled)..."

# Instagram — Mon/Wed/Fri 11:00
$igTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Wednesday,Friday -At 11:00am
Register-HPTask "HP-Instagram-AutoPost" $igBat $igTrigger

# TikTok — Monday 10:30 (weekly batch upload to TikTok's own scheduler)
$ttTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 10:30am
Register-HPTask "HP-TikTok-AutoPost" $ttBat $ttTrigger

Write-Host ""
Write-Host "DONE  Timers installed. The PC must be plugged in and ASLEEP (not shut"
Write-Host "down) at those times — Windows will wake it, post, and let it sleep again."
Write-Host "View tasks:  Get-ScheduledTask -TaskName 'HP-*'"
Write-Host "Test now:    Start-ScheduledTask -TaskName 'HP-Instagram-AutoPost'"
