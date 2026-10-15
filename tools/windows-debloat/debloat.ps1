# Removes Microsoft apps you don't use when you live in Google Workspace.
# DRY RUN by default: prints what it would remove. Add -Apply to actually remove.
# Run in PowerShell as Administrator:  .\debloat.ps1        (preview)
#                                      .\debloat.ps1 -Apply (remove)
param([switch]$Apply)

# Store/UWP apps (safe to remove; reinstallable from Microsoft Store)
$appx = @(
  'Microsoft.Copilot','Microsoft.Windows.Ai.Copilot.Provider','Microsoft.549981C3F5F10', # Copilot / Cortana
  'Microsoft.MicrosoftOfficeHub','Microsoft.Office.OneNote','Microsoft.OutlookForWindows',
  'Microsoft.Office.Desktop.Word','Microsoft.Office.Desktop.Excel','Microsoft.Office.Desktop.PowerPoint',
  'MSTeams','Microsoft.Teams','Clipchamp.Clipchamp','Microsoft.MicrosoftSolitaireCollection',
  'Microsoft.BingNews','Microsoft.BingWeather','Microsoft.GetHelp','Microsoft.Getstarted',
  'Microsoft.MicrosoftStickyNotes','Microsoft.People','Microsoft.WindowsFeedbackHub',
  'Microsoft.XboxGamingOverlay','Microsoft.XboxIdentityProvider','Microsoft.GamingApp',
  'Microsoft.YourPhone','Microsoft.ZuneMusic','Microsoft.ZuneVideo','MicrosoftCorporationII.QuickAssist',
  'Microsoft.Todos','Microsoft.PowerAutomateDesktop','Microsoft.MicrosoftJournal'
)

# Classic desktop Office (Word, Excel, PowerPoint, Outlook, OneNote, Teams)
$wingetIds = @('Microsoft.Office','Microsoft.Teams','Microsoft.OneDrive')

# Safety: don't touch Edge settings unless Chrome is installed
$chrome = (Test-Path "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") -or
          (Test-Path "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe")


# ---- RAM report (read-only, always runs) ----
$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
$freeGB  = [math]::Round($os.FreePhysicalMemory/1MB,1)
Write-Host ("RAM: {0} GB total, {1} GB used, {2} GB free" -f $totalGB, ($totalGB-$freeGB), $freeGB) -ForegroundColor Green
Write-Host "Top 15 processes by RAM:" -ForegroundColor Green
Get-Process | Group-Object ProcessName | ForEach-Object {
  [pscustomobject]@{Name=$_.Name; Count=$_.Count; MB=[math]::Round(($_.Group | Measure-Object WorkingSet64 -Sum).Sum/1MB)}
} | Sort-Object MB -Descending | Select-Object -First 15 | Format-Table -AutoSize
Write-Host "Startup items:" -ForegroundColor Green
Get-CimInstance Win32_StartupCommand | Select-Object Name, Command | Format-Table -AutoSize -Wrap

Write-Host ("Mode: " + $(if($Apply){'APPLY'}else{'DRY RUN (add -Apply to remove)'})) -ForegroundColor Cyan

foreach ($n in $appx) {
  $found = Get-AppxPackage -AllUsers -Name $n -ErrorAction SilentlyContinue
  foreach ($p in $found) {
    Write-Host "Appx: $($p.Name)"
    if ($Apply) { Remove-AppxPackage -Package $p.PackageFullName -AllUsers -ErrorAction SilentlyContinue }
  }
}

foreach ($id in $wingetIds) {
  if (winget list --id $id --exact 2>$null | Select-String $id) {
    Write-Host "Winget: $id"
    if ($Apply) { winget uninstall --id $id --exact --silent --disable-interactivity }
  }
}

# ---- Edge: block background/startup, then try to uninstall (only if Chrome exists) ----
if ($chrome) {
  Write-Host "Edge: disable startup/background, attempt uninstall (Chrome found)"
  if ($Apply) {
    $k = 'HKLM:\SOFTWARE\Policies\Microsoft\Edge'
    New-Item -Path $k -Force | Out-Null
    Set-ItemProperty $k -Name StartupBoostEnabled -Value 0 -Type DWord
    Set-ItemProperty $k -Name BackgroundModeEnabled -Value 0 -Type DWord
    Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force
    $setup = Get-ChildItem "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\*\Installer\setup.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($setup) {
      & $setup.FullName --uninstall --system-level --force-uninstall --verbose-logging
      Write-Host "Edge uninstall attempted. Windows may block it or reinstall it on update." -ForegroundColor Yellow
    }
    # stop Edge update tasks/services
    Get-ScheduledTask -TaskName 'MicrosoftEdgeUpdate*' -ErrorAction SilentlyContinue | Disable-ScheduledTask | Out-Null
    foreach ($svc in 'edgeupdate','edgeupdatem') { Set-Service $svc -StartupType Disabled -ErrorAction SilentlyContinue; Stop-Service $svc -Force -ErrorAction SilentlyContinue }
  }
} else { Write-Host "Chrome not found - leaving Edge alone." -ForegroundColor Yellow }

# ---- Bing: remove web results/Bing from Start search, disable Search highlights ----
Write-Host "Bing: disabling web search in Start + search highlights"
if ($Apply) {
  $e = 'HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer'
  New-Item -Path $e -Force | Out-Null
  Set-ItemProperty $e -Name DisableSearchBoxSuggestions -Value 1 -Type DWord
  $s = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\SearchSettings'
  New-Item -Path $s -Force | Out-Null
  Set-ItemProperty $s -Name IsDynamicSearchBoxEnabled -Value 0 -Type DWord
  Set-ItemProperty $s -Name IsAADCloudSearchEnabled -Value 0 -Type DWord
  Set-ItemProperty $s -Name IsMSACloudSearchEnabled -Value 0 -Type DWord
}

# ---- Background tasks: stop UWP apps running in background, drop Microsoft startup entries ----
Write-Host "Background: disabling background apps + Microsoft startup entries"
if ($Apply) {
  $b = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications'
  New-Item -Path $b -Force | Out-Null
  Set-ItemProperty $b -Name GlobalUserDisabled -Value 1 -Type DWord
  $run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
  foreach ($n in 'OneDrive','MicrosoftEdgeAutoLaunch*','Teams','com.squirrel.Teams.Teams') {
    Get-Item $run -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Property | Where-Object { $_ -like $n } |
      ForEach-Object { Remove-ItemProperty $run -Name $_ -ErrorAction SilentlyContinue }
  }
  # Telemetry/diagnostics services that eat RAM/CPU
  foreach ($svc in 'DiagTrack','dmwappushservice') { Set-Service $svc -StartupType Disabled -ErrorAction SilentlyContinue; Stop-Service $svc -Force -ErrorAction SilentlyContinue }
}

Write-Host "Done. Restart to finish." -ForegroundColor Cyan
