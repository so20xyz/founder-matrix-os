# Cut-over runbook: PC / Windows (OSB → fm plugin)

`cutover-mac.md`-тэй ижил шилжилт, Windows PowerShell-ээр. **Mac 1 өдөр тогтвортой ажилласны дараа** л эхэл. Алхам бүр буцаагдана: бүх зүйл `$BK` руу хуулагдаж/зөөгдөнө, юу ч устгахгүй.

- **Зөвхөн PC бичнэ** энэ хугацаанд: Mac дээр Obsidian ба Claude сешнүүдийг хаа (Drive `(1)` давхардлаас сэргийлнэ).
- **Relay өгөгдлийг PC дээр ДАХИН шилжүүлэхгүй.** Mac 6-р алхамд `_system/fm/`-г vault-д бичсэн; PC түүнийг Google Drive-аар авна. Энд зөвхөн байгаа эсэхийг шалгана.
- PC-ийн амьд `settings.json`-ийг өмнө нь хэн ч уншаагүй — 3-р алхмын dry-run-ийг заавал уншиж шалга.
- Хүрэхгүй: `.obsidian/`, `tools\relay\` код, Discord суваг.

## 0. Хувьсагч ба урьдчилсан шалгалт

PowerShell (энгийн хэрэглэгчээр, admin биш) нэг цонхонд бүх алхмыг хий.

```powershell
$Date  = Get-Date -Format yyyy-MM-dd
$BK    = "$env:USERPROFILE\Backups\fm-cutover-$Date"
$Claude = "$env:USERPROFILE\.claude"
# Vault: Google Drive-ийн үсгийг (D:, G: ...) автоматаар олно
$Vault = Get-PSDrive -PSProvider FileSystem | ForEach-Object { Join-Path $_.Root 'My Drive\Second Brain 2.0' } |
         Where-Object { Test-Path (Join-Path $_ '.obsidian') } | Select-Object -First 1
$Repo  = '<founder-matrix-os checkout-ийн бүтэн зам>'   # жишээ: <диск>:\CodeBase\founder-matrix-os, fm-v02 merge хийгдсэн
$Shims = 'obsidian-save','obsidian-inbox','obsidian-route','obsidian-project','obsidian-daily','obsidian-world','obsidian-log','track','jirge','sync','01-project-admin'

"vault: $Vault"
Test-Path "$Repo\plugins\fm\.claude-plugin\plugin.json"   # True
Test-Path "$Repo\extras\aliases"                          # True
git -C $Repo log -1 --oneline
python3 --version                                         # 3.9+ — ЗААВАЛ python3.exe
```

**`python3` олдохгүй бол** (python.org installer зөвхөн `python.exe`/`py.exe` суулгадаг) fm hook-ууд ажиллахгүй. Нэгийг сонго:
1. `uv python install --default` (санал болгох) → `%USERPROFILE%\.local\bin` PATH-д байгаа эсэхийг шалга.
2. Microsoft Store Python 3.x (Settings › App execution aliases нь Store stub биш байх).
3. Python хавтсанд `python.exe`-г `python3.exe` нэрээр хуулах.

Шинэ PowerShell нээж `python3 --version` дахин шалга. `$Vault` хоосон эсвэл `False` гарвал **зогс**.

Discord `#03-sys-admin`-д зарла: «PC cut-over эхэллээ — зөвхөн PC бичнэ».

## 1. Backup (Drive-аас гадуур)

```powershell
New-Item -ItemType Directory -Force "$BK\claude\plugins","$BK\vault","$BK\moved-skills","$BK\moved-commands","$BK\rolled-back" | Out-Null
Copy-Item "$Claude\settings.json" "$BK\claude\"
Copy-Item "$Claude\commands" "$BK\claude\commands" -Recurse
Copy-Item "$Claude\skills"   "$BK\claude\skills"   -Recurse
foreach ($d in 'agents','scheduled-tasks') { if (Test-Path "$Claude\$d") { Copy-Item "$Claude\$d" "$BK\claude\$d" -Recurse } }
Copy-Item "$Claude\plugins\*.json" "$BK\claude\plugins\"
Copy-Item "$env:USERPROFILE\.claude.json" "$BK\claude.json"
if (Test-Path "$env:USERPROFILE\.fmos\config.json") { Copy-Item "$env:USERPROFILE\.fmos\config.json" "$BK\fmos-config.json" }
Copy-Item "$Vault\04-Areas\AI Team\ai-workers" "$BK\vault\ai-workers" -Recurse
Get-FileHash "$Claude\settings.json" | Select-Object -ExpandProperty Hash | Set-Content "$BK\settings-sha256-before.txt"
Get-ChildItem "$Claude\commands" -Name | Set-Content "$BK\commands-before.txt"
Get-ChildItem "$Claude\skills"   -Name | Set-Content "$BK\skills-before.txt"
Get-ScheduledTask | Where-Object { $_.TaskName -match 'fmos|dispatcher|relay|harvest' } |
  ForEach-Object { Export-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath | Set-Content "$BK\task-$($_.TaskName).xml" }
Get-ChildItem $BK
```

> `$BK\claude.json` нууц агуулна — Drive, git, Discord руу бүү хуул.

**Буцаах:** энэ алхам юу ч өөрчлөөгүй.

## 2. Plugin суулгах (local repo-оос)

```powershell
claude plugin validate $Repo
claude plugin validate "$Repo\plugins\fm"
claude plugin marketplace add $Repo
claude plugin install fm@founder-matrix --config "vault_path=$Vault" --config "member=itge.e" --config "device=PC"
claude plugin list | Select-String "fm@founder-matrix"
```

`validate` алдаа өгвөл **зогс**. `--config` танигдахгүй бол түүнгүйгээр суулгаад `/plugin` → `fm` → Configure дээр бөглө.

**Буцаах:**
```powershell
claude plugin uninstall fm@founder-matrix
claude plugin marketplace remove founder-matrix
```

## 3. `settings.json`: OSB hook-уудыг хасах

```powershell
python3 "$Repo\extras\cutover_settings.py"            # dry-run — гаралтыг УНШ
python3 "$Repo\extras\cutover_settings.py" --apply
python3 "$Repo\extras\cutover_settings.py" --check                     # exit 0
python3 -m json.tool "$Claude\settings.json" > $null; if ($?) { "JSON OK" }
```

- Скрипт `obsidian-second-brain\hooks\*` (load_vault_context, validate-ai-first, obsidian-bg-agent) ба `check-write-date.sh`-ийг хасна; `relay.py`, `status.py`, `claude_status.py` үлдэнэ; CRLF ба догол хадгалагдана.
- Dry-run-д хуучин vault замтай (`Founder.Matrix`) hook харагдвал **энэ скрипт хөндөхгүй** — `claude_status.py`-г repo хуулбар руу (`$Repo\tools\figma\bridge\claude_status.py`) заах эсэхийг Tool Developer-ээс асуу, гараар зас.
- `OBSIDIAN_VAULT_PATH` хуучин замтай байвал `$Vault` болгож гараар зас (`relay.py` уншдаг).

> ⚠️ `--vault` **бүү** өг (`FM_VAULT`-ийг settings.json-д бүү нэм): settings-ийн env бүх hook-д очдог тул relay 7-р алхмаас **өмнө** vault горимд шилжиж, `_system/fm/` хоосон байхад registry/discord.json-гүй болно; 7-р алхмын «Буцаах» ч ажиллахгүй болно. Горимын цорын ганц шилжүүлэгч = `~/.fmos/config.json` (7-р алхам). Plugin vault-аа `vault_path`/`config.json`-оос олно.

**Буцаах:** `Copy-Item "$BK\claude\settings.json" "$Claude\settings.json" -Force`

## 4. Commands: OSB хуулбар → shim

PC дээр командууд symlink биш **хуулбар** байж магадгүй тул OSB-ийн командын нэрсийн жагсаалтаар тааруулна (энэ алхмыг 5-аас **өмнө** хий).

```powershell
$OsbNames = Get-ChildItem "$Claude\skills\obsidian-second-brain\commands" -Name -Filter *.md
Get-ChildItem "$Claude\commands" -Filter *.md | Where-Object { $OsbNames -contains $_.Name } |
  Move-Item -Destination "$BK\moved-commands\"
foreach ($f in 'obsidian-inbox.md','obsidian-route.md','track.md','jirge.md','sync.md','01-project-admin.md') {
  if (Test-Path "$Claude\commands\$f") { Move-Item "$Claude\commands\$f" "$BK\moved-commands\" }
}
Get-ChildItem "$Claude\commands" -Filter '01-project-admin.md.bak-*' | Move-Item -Destination "$BK\moved-commands\"
foreach ($n in $Shims) { Copy-Item "$Repo\extras\aliases\$n.md" "$Claude\commands\" }
Get-ChildItem "$Claude\commands" -Name
```

**Шалгах:** 11 shim байгаа, `obsidian-*` нэртэй бусад файл үлдээгүй.

**Буцаах:**
```powershell
foreach ($n in $Shims) { Remove-Item "$Claude\commands\$n.md" -ErrorAction SilentlyContinue }
Move-Item "$BK\moved-commands\*" "$Claude\commands\"
```

## 5. OSB skill ба kepano хуулбаруудыг backup руу зөөх

```powershell
foreach ($s in 'obsidian-second-brain','defuddle','json-canvas','obsidian-bases','obsidian-cli','obsidian-markdown','diagram-design') {
  if (Test-Path "$Claude\skills\$s") { Move-Item "$Claude\skills\$s" "$BK\moved-skills\" }
}
Get-ChildItem "$BK\moved-skills" -Name
```

Эдгээр kepano skill-ийг fm v0.3 хуулдаггүй: зөөхөөс **өмнө** албан ёсны plugin-ийг суулга — `/plugin marketplace add kepano/obsidian-skills` → `/plugin install obsidian@obsidian-skills`.

OSB хавтас дотор ажиллаж буй MCP процесс файл түгжвэл: бүх Claude цонхыг хаагаад дахин ажиллуул.

**Буцаах:** `Move-Item "$BK\moved-skills\*" "$Claude\skills\"`

## 6. Relay өгөгдөл: зөвхөн шалгах

```powershell
Get-ChildItem "$Vault\_system\fm" -Name      # registry.json, channels.json, discord.json, state
python3 -c "import json,sys;print(len(json.load(open(sys.argv[1],encoding='utf-8'))['sessions']))" "$Vault\_system\fm\registry.json"
```

Файлууд алга бол Drive sync дуусаагүй байна — хүлээ. `migrate_to_vault.py --apply`-г PC дээр **бүү** ажиллуул (хоёр бичигч болно).

## 7. `~/.fmos/config.json`

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.fmos" | Out-Null
python3 -c "import json,sys,pathlib;p=pathlib.Path.home()/'.fmos'/'config.json';print('байна, дарж бичсэнгүй') if p.exists() else p.write_text(json.dumps({'vault':sys.argv[1],'device':'PC','member':'itge.e'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')" "$Vault"
Get-Content "$env:USERPROFILE\.fmos\config.json" -Encoding UTF8
```

**Буцаах:** `Move-Item "$env:USERPROFILE\.fmos\config.json" "$BK\rolled-back\fmos-config.json"` (хуучин байсан бол `$BK\fmos-config.json`-ийг буцааж хуул).

## 8. Dispatcher (Task Scheduler) дахин эхлүүлэх

```powershell
$Tasks = Get-ScheduledTask | Where-Object { $_.TaskName -match 'fmos|dispatcher' }
$Tasks | Format-Table TaskName, State
$Tasks | ForEach-Object { Stop-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath; Start-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath }
Start-Sleep 3
Get-ScheduledTask | Where-Object { $_.TaskName -match 'fmos|dispatcher' } | Format-Table TaskName, State   # Running
Get-Process node -ErrorAction SilentlyContinue | Format-Table Id, StartTime
```

Task олдохгүй бол dispatcher-ийг гараар ажиллуулдаг байж магадгүй — ажиллаж буй `node ... dispatcher.mjs` цонхыг хааж дахин эхлүүл. PC бол Discord-ийн үндсэн бичигч (`FMOS_WRITER`) тул энэ алхмыг алгасахгүй.

**Буцаах:** ижил Stop/Start (task XML-ийг өөрчлөөгүй тул тохиргоо хэвээр; хэрэгтэй бол `Register-ScheduledTask -Xml (Get-Content "$BK\task-<нэр>.xml" -Raw) -TaskName <нэр> -Force`).

## 9. Шалгалт (шинэ сешнээр)

`cd $Vault; claude` — шинэ сешн нээгээд `cutover-mac.md` 9-р алхмын хүснэгтийн 1–6-г давт. Терминалаас:

```powershell
python3 "$Repo\extras\cutover_settings.py" --check                                        # exit 0
python3 "$Repo\plugins\fm\scripts\fm_lint.py" "$Vault\_system\BOOT.md" --vault "$Vault"   # үр дүн цэвэр
'{"session_id":"cutover-check","cwd":"' + ($Vault -replace '\\','/') + '"}' | python3 "$Repo\plugins\fm\scripts\fm_context.py"
(Get-ChildItem "$Claude\commands" -Name | Where-Object { $Shims -contains ($_ -replace '\.md$','') }).Count   # 11
```

Hook алдаа (`python3` not found) гарвал 0-р алхмын python3 засварыг хий. Амжилттай бол `#03-sys-admin`-д: «PC cut-over дууслаа».

## 10. Бүрэн буцаалт (урвуу дарааллаар)

```powershell
if (Test-Path "$env:USERPROFILE\.fmos\config.json") { Move-Item "$env:USERPROFILE\.fmos\config.json" "$BK\rolled-back\fmos-config.json" -Force }
if (Test-Path "$BK\fmos-config.json") { Copy-Item "$BK\fmos-config.json" "$env:USERPROFILE\.fmos\config.json" }
Move-Item "$BK\moved-skills\*" "$Claude\skills\"
foreach ($n in $Shims) { Remove-Item "$Claude\commands\$n.md" -ErrorAction SilentlyContinue }
Move-Item "$BK\moved-commands\*" "$Claude\commands\"
Copy-Item "$BK\claude\settings.json" "$Claude\settings.json" -Force
claude plugin uninstall fm@founder-matrix
claude plugin marketplace remove founder-matrix
Copy-Item "$BK\claude\plugins\*.json" "$Claude\plugins\" -Force
Get-ScheduledTask | Where-Object { $_.TaskName -match 'fmos|dispatcher' } | ForEach-Object { Stop-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath; Start-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath }
```

**Буцаалтыг шалгах:**
```powershell
(Get-FileHash "$Claude\settings.json").Hash -eq (Get-Content "$BK\settings-sha256-before.txt")   # True
Compare-Object (Get-Content "$BK\commands-before.txt") (Get-ChildItem "$Claude\commands" -Name)    # хоосон
Compare-Object (Get-Content "$BK\skills-before.txt")   (Get-ChildItem "$Claude\skills" -Name)      # хоосон
```

Vault-ийн `_system/fm/` (Mac бичсэн) PC-ийн буцаалтад хамаарахгүй — Mac-ийн 10-р алхмаар л буцна.

## 11. Дараа нь

- **2026-11-05:** `foreach ($n in $Shims) { Remove-Item "$Claude\commands\$n.md" }`.
- **30 хоногийн дараа** бүх зүйл тогтвортой бол `$BK`-г устга.
