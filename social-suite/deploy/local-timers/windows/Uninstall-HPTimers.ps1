# Removes the HP Task Scheduler jobs.
#   powershell -ExecutionPolicy Bypass -File .\Uninstall-HPTimers.ps1
$ErrorActionPreference = "SilentlyContinue"
foreach ($name in @("HP-Instagram-AutoPost", "HP-TikTok-AutoPost")) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false
  Write-Host "removed $name"
}
Write-Host "DONE  Timers removed."
