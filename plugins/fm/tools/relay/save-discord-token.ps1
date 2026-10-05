# Copy the Discord bot token (Ctrl+C), then run this. Saves to ~/.fmos_discord_token (outside repo/vault).
$t = ((Get-Clipboard -Raw) | Out-String).Trim()
$dots = ($t.ToCharArray() | Where-Object { $_ -eq '.' }).Count
if ($t.Length -lt 50 -or $dots -ne 2 -or $t -match '\s') {
  Write-Host "Clipboard does not look like a Discord token (length=$($t.Length), dots=$dots). Copy the token again." -ForegroundColor Yellow; exit 1 }
Set-Content -Path "$HOME\.fmos_discord_token" -Value $t -NoNewline -Encoding ascii
Set-Clipboard -Value " "
Write-Host "Saved: $HOME\.fmos_discord_token (length=$($t.Length)); clipboard cleared." -ForegroundColor Green
