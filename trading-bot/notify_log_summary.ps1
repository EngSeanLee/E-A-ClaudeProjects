# Quick keyword-scan of today's bot log, shown as a Windows desktop
# notification. This is a dumb summary (counts, not reasoning) — for an
# actual explanation of WHY something happened, ask Claude Code directly
# and it'll read + interpret the log properly.

$logDir = "C:\Users\EngSean Lee\E-A-ClaudeProjects\trading-bot\logs"
$today = Get-Date -Format "yyyy-MM-dd"
$logFile = Join-Path $logDir "$today.log"

if (-not (Test-Path $logFile)) {
    $summary = "No log file for $today yet - the scheduled run may not have fired."
} else {
    $lines = Get-Content $logFile
    $buys = ($lines | Select-String "SUBMIT BUY").Count
    $sells = ($lines | Select-String "SUBMIT SELL|CLOSE POSITION").Count
    $errors = ($lines | Select-String "\[ERROR\]").Count
    $warnings = ($lines | Select-String "\[WARNING\]").Count
    $breaker = ($lines | Select-String "circuit breaker").Count

    $summary = "Buys: $buys  Sells: $sells  Warnings: $warnings  Errors: $errors"
    if ($breaker -gt 0) { $summary = "CIRCUIT BREAKER MENTIONED - $summary" }
}

Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.BalloonTipTitle = "Trading Bot - $today"
$notify.BalloonTipText = $summary
$notify.ShowBalloonTip(15000)
Start-Sleep -Seconds 16
$notify.Dispose()
