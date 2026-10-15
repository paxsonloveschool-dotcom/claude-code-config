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

# Edge can't be fully uninstalled on current Windows 11 (system component).
# Instead: stop it launching at startup and running in the background.
if ($chrome) {
  Write-Host "Edge: disabling startup boost + background run (Chrome found)"
  if ($Apply) {
    $k = 'HKLM:\SOFTWARE\Policies\Microsoft\Edge'
    New-Item -Path $k -Force | Out-Null
    Set-ItemProperty $k -Name StartupBoostEnabled -Value 0 -Type DWord
    Set-ItemProperty $k -Name BackgroundModeEnabled -Value 0 -Type DWord
  }
} else { Write-Host "Chrome not found - leaving Edge alone." -ForegroundColor Yellow }

Write-Host "Done. Restart to finish." -ForegroundColor Cyan
