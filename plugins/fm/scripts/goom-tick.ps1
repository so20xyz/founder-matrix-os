# goom-tick (эх: founder-matrix-os/plugins/fm/scripts/goom-tick.ps1; ~/.fmos/goom-tick.ps1 нь нэг мөрийн shim) — 2 минут тутам: (1) локал туршилтын токеныг шинэчилнэ (1 цагаас бага үлдсэн бол), (2) Удирдлагын өрөөнд snapshot илгээнэ.
# Зөвхөн локал dev Goomnet (localhost:3000) ба туршилтын хэрэглэгч (backend/dev-login.txt). Зогсоох: Unregister-ScheduledTask -TaskName goom-tick -Confirm:$false
$cfgPath = "$env:USERPROFILE\.fmos\goom.json"
$login = "D:\CodeBase\goomnet\backend\dev-login.txt"
try {
  $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
  $p = $cfg.token.Split('.')[1].Replace('-', '+').Replace('_', '/'); while ($p.Length % 4) { $p += '=' }
  $exp = ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p)) | ConvertFrom-Json).exp
  if ($exp - [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() -lt 3600 -and (Test-Path $login)) {
    $l = Get-Content $login; $email = ($l | Where-Object { $_ -like 'email:*' } | Select-Object -First 1) -replace 'email:\s*', ''; $pw = ($l | Where-Object { $_ -like 'password:*' } | Select-Object -First 1) -replace 'password:\s*', ''
    $r = Invoke-RestMethod -TimeoutSec 15 -Method Post "$($cfg.url)/api/web/public/login/" -ContentType 'application/json' -Body (@{ email = $email; password = $pw } | ConvertTo-Json)
    $cfg.token = $r.JWT; [IO.File]::WriteAllText($cfgPath, ($cfg | ConvertTo-Json))  # BOM-гүй (Python json BOM-д унадаг)
  }
} catch {}
& python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_control.py" --once *> $null
& python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_board.py" status 5 *> $null
& python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_pull.py" "D:/My Drive/Second Brain 2.0" --apply *>> "$env:USERPROFILE\.fmos\goom-pull.log"
if ((Get-Date).Minute -lt 2) { & python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_github_inbox.py" "D:/My Drive/Second Brain 2.0" --apply *>> "$env:USERPROFILE\.fmos\github-inbox.log" }
& python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_agents.py" scan *>> "$env:USERPROFILE\.fmos\agents.log"  # agent heartbeat (~/.fmos/agents) -> Goom header
& python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_reminders.py" tick *>> "$env:USERPROFILE\.fmos\reminders.log"  # itge.e-ийн task сануулга + 07:30 жагсаалт -> Discord #сануулга (2026-11-02)
& python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_chat.py" sync-sessions *>> "$env:USERPROFILE\.fmos\goom-sync.log"
# --full цагт нэг (itge.e 2026-11-02): зөөсөн/устгасан note-ийг DB-ээс soft-delete; өмнө нь хэзээ ч ажилладаггүй байсан тул 23 хуучин мөр үлдэв
$full = @(); if ((Get-Date).Minute -lt 2) { $full = @('--full') }
if ((Get-Date).Minute % 10 -lt 2) { & python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_sync.py" "D:/My Drive/Second Brain 2.0" --apply @full *>> "$env:USERPROFILE\.fmos\goom-sync-vault.log"; & python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_parity.py" "D:/My Drive/Second Brain 2.0" --list 0 *>> "$env:USERPROFILE\.fmos\goom-parity.log" }  # vault -> Goom, 10 min (safety net) + mirror parity report
# Mirror watcher (decision 2026-10-25): one long-lived hidden process, vault -> DB within ~15 s. Lock file in fm_goom_watch.py
# makes duplicate starts exit at once, so starting it every tick is safe. PC only (Drive: one writer machine).
try {
  $pyw = Join-Path (Split-Path (& python -c 'import sys;print(sys.executable)')) 'pythonw.exe'
  if (Test-Path $pyw) { Start-Process -FilePath $pyw -WindowStyle Hidden -ArgumentList @('"D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_watch.py"', '"D:/My Drive/Second Brain 2.0"') }
} catch {}
# Second Brain чат гацалт (2026-10-23): itge.e-ийн мессеж >=3 мин хариугүй -> сешний Discord суваг + Windows toast (шинэ гацалт бүрд нэг удаа)
try {
  $st = & python "D:\CodeBase\founder-matrix-os\plugins\fm\scripts\fm_goom_chat.py" stall-check 2>> "$env:USERPROFILE\.fmos\goom-stall.log"
  foreach ($line in $st) {
    $r = $line | ConvertFrom-Json
    Add-Content -Encoding utf8 "$env:USERPROFILE\.fmos\goom-stall.log" "$(Get-Date -Format s) $line"
    if ($r.new) {
      [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
      $x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
      $t = $x.GetElementsByTagName('text')
      [void]$t.Item(0).AppendChild($x.CreateTextNode('Second Brain: хариугүй чат'))
      [void]$t.Item(1).AppendChild($x.CreateTextNode("«$($r.title)» (chat $($r.chat_id)) — $($r.count) мессеж хүлээж байна"))
      [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Second Brain').Show([Windows.UI.Notifications.ToastNotification]::new($x))
    }
  }
} catch {}