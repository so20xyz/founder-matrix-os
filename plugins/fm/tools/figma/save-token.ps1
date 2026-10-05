# Copy your Figma personal access token first, then run this. Saves it to ~/.figma_token (outside the vault).
$t = (Get-Clipboard | Out-String).Trim()
if ($t -notmatch '^figd_[\w\-]+$') { Write-Host "No Figma token (figd_...) in clipboard." -ForegroundColor Yellow; exit 1 }
Set-Content -Path "$HOME\.figma_token" -Value $t -NoNewline -Encoding ascii
Write-Host "Saved to $HOME\.figma_token"
python "$PSScriptRoot\figma.py" me
