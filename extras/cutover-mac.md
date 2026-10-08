# Cut-over runbook: Mac (OSB → fm plugin)

itge.e-ийн Mac-ийг хуучин `obsidian-second-brain` (OSB) тохиргооноос `fm@founder-matrix` plugin руу шилжүүлэх заавар. Алхмуудыг **дарааллаар нь** хий. Алхам бүр буцаагдана: бүх зүйл эхлээд `$BK` руу хуулагдана, юу ч устгахгүй (зөвхөн `mv`).

- **Хугацаа:** ~30 минут. Дараа нь Mac дээр 1 өдөр тогтвортой ажиллуулаад PC-г шилжүүлнэ (`cutover-pc.md`).
- **Хүрэхгүй:** `.obsidian/`, `tools/relay/` код, `fmos-harvester-mac` scheduled task, Discord суваг.
- **Зөвхөн Mac бичнэ.** PC дээр Obsidian ба Claude сешнүүдийг хаа (Drive `(1)` давхардлаас сэргийлнэ) — **PC cut-over хүртэл хаалттай байлга**: legacy PC-ийн baton/бүртгэл git `state/`, `relay/` руу очиж vault-ийн `_system/fm/`-д хэзээ ч орохгүй, STATUS хоёр эх сурвалжаас ээлжлэн дарагдана.

## 0. Хувьсагч ба урьдчилсан шалгалт

Нэг терминал цонхонд бүх алхмыг хий (хувьсагчид хадгалагдана). Шинэ цонх нээвэл энэ блокийг дахин ажиллуул. ⚠️ Командууд **bash**-д зориулагдсан (zsh `$SHIMS`-ийг задалдаггүй, олдоогүй glob дээр зогсдог) — эхлээд `bash` гэж бичиж ор.

```bash
bash          # zsh-ээс bash руу (prompt солигдоно), дараа нь доорхыг
DATE=$(date +%F)
BK="$HOME/Backups/fm-cutover-$DATE"
VAULT="$HOME/My Drive/Second Brain 2.0"
REPO="$HOME/Documents/CodeBase/founder-matrix-os"   # fm-v02 merge хийгдсэн main checkout
SHIMS="obsidian-save obsidian-inbox obsidian-route obsidian-project obsidian-daily obsidian-world obsidian-log track jirge sync 01-project-admin"

test -d "$VAULT/.obsidian"                 && echo "vault OK"
test -f "$REPO/plugins/fm/.claude-plugin/plugin.json" && echo "plugin OK"
test -d "$REPO/extras/aliases"             && echo "aliases OK"
git -C "$REPO" log -1 --oneline
python3 --version                          # 3.9+
```

Аль нэг нь `OK` гэж хэвлэхгүй бол **зогс**: `REPO` дээр `fm-v02` merge хийгдээгүй байна.

- Discord `#03-sys-admin`-д зарла: «fm cut-over эхэллээ — зөвхөн Mac бичнэ, PC сешнүүдийг хаалаа».
- Ажиллаж буй Claude сешнүүд хуучин context-оороо үргэлжилнэ; шинэ hook-ууд зөвхөн шинэ/resume хийсэн сешнд ажиллана.

## 1. Backup (Drive-аас гадуур)

```bash
mkdir -p "$BK/claude/plugins" "$BK/vault" "$BK/repo" "$BK/moved-skills" "$BK/moved-commands" "$BK/rolled-back"
chmod 700 "$BK"
cp -p  ~/.claude/settings.json            "$BK/claude/"
cp -pR ~/.claude/commands                 "$BK/claude/commands"        # symlink-ууд symlink хэвээр хуулагдана
cp -pR ~/.claude/skills                   "$BK/claude/skills"
[ -d ~/.claude/agents ]          && cp -pR ~/.claude/agents          "$BK/claude/agents"
[ -d ~/.claude/scheduled-tasks ] && cp -pR ~/.claude/scheduled-tasks "$BK/claude/scheduled-tasks"
cp -p  ~/.claude/plugins/*.json           "$BK/claude/plugins/"
cp -p  ~/.claude.json                     "$BK/claude.json"
cp -p  ~/Library/LaunchAgents/com.fmos.dispatcher.plist "$BK/"
[ -f ~/.fmos/config.json ] && cp -p ~/.fmos/config.json "$BK/fmos-config.json"
cp -pR "$VAULT/03-Areas/AI Team/ai-workers" "$BK/vault/ai-workers"
[ -d "$VAULT/_system/fm" ] && cp -pR "$VAULT/_system/fm" "$BK/vault/fm"
cp -pR "$REPO/relay" "$BK/repo/relay"
[ -d "$REPO/state" ] && cp -pR "$REPO/state" "$BK/repo/state"
shasum -a 256 ~/.claude/settings.json ~/.claude.json > "$BK/sha256-before.txt"
ls -la ~/.claude/commands > "$BK/commands-before.txt"
ls -la ~/.claude/skills   > "$BK/skills-before.txt"
du -sh "$BK"
```

**Шалгах:** `du -sh` ~190 MB орчим (OSB skill 157 MB). `ls "$BK/claude/commands" | wc -l` = 59.

> `$BK/claude.json` болон `$BK/repo/relay/` нууц/ID агуулна — `$BK`-г Drive, git, Discord руу хэзээ ч бүү хуул.

**Буцаах:** энэ алхам юу ч өөрчлөөгүй.

## 2. Plugin суулгах (local repo-оос)

```bash
claude plugin validate "$REPO"
claude plugin validate "$REPO/plugins/fm"
claude plugin marketplace add "$REPO"
claude plugin install fm@founder-matrix \
  --config vault_path="$VAULT" --config member="itge.e" --config device="Mac"
claude plugin list | grep -i "fm@founder-matrix"
```

- `validate` алдаа (✘) өгвөл **зогс**, Tool Developer-т мэдэгд.
- `--config` танигдахгүй бол `--config`-гүйгээр суулгаад, шинэ сешнд `/plugin` → `fm` → Configure дээр `vault_path`-ийг бөглө.
- Энэ мөчөөс хуучин OSB ба `fm` зэрэгцэн ажиллана (namespace мөргөлдөхгүй: `/fm:*` ба `/obsidian-*`).

**Буцаах:**
```bash
claude plugin uninstall fm@founder-matrix
claude plugin marketplace remove founder-matrix
```

## 3. `settings.json`: OSB hook-уудыг хасах

Хасагдах 4 hook: SessionStart `load_vault_context.py`, PostCompact `obsidian-bg-agent.sh`, PostToolUse `validate-ai-first.sh` ба `check-write-date.sh` (`fm_lint.py`-д шингэсэн). **Үлдэх:** `relay.py inbox/baton`, `status.py`, `claude_status.py` (13 hook). Зорилтот төлөв: `extras/settings.mac.json.example`.

```bash
python3 "$REPO/extras/cutover_settings.py"            # dry-run: 4 мөр хасахыг харуулна
python3 "$REPO/extras/cutover_settings.py" --apply
python3 "$REPO/extras/cutover_settings.py" --check                     # "OK: ... алга", exit 0
python3 -m json.tool ~/.claude/settings.json > /dev/null && echo "JSON OK"
grep -c "relay.py\|status.py\|claude_status.py" ~/.claude/settings.json   # 13
```

> ⚠️ `--vault` **бүү** өг (`FM_VAULT`-ийг settings.json-д бүү нэм): settings-ийн env бүх hook-д очдог тул relay 6-р алхмаас **өмнө** vault горимд шилжиж, `_system/fm/` хоосон байхад registry/discord.json-гүй болно; 6-р алхмын «Буцаах» ч ажиллахгүй болно. Горимын цорын ганц шилжүүлэгч = `~/.fmos/config.json` (6–7-р алхам). Plugin vault-аа `vault_path`/`config.json`-оос олно.

`OBSIDIAN_VAULT_PATH` хэвээр үлдэнэ (`relay.py` уншдаг). `AI_FIRST_SKIP_CHARSET` хоргүй — 30 хоногийн цэвэрлэгээнд хасна.

**Буцаах:** `cp -p "$BK/claude/settings.json" ~/.claude/settings.json`

## 4. OSB skill ба kepano хуулбаруудыг backup руу зөөх

```bash
cd ~/.claude/skills
mv obsidian-second-brain "$BK/moved-skills/"          # plugin hooks.json, vault MCP, obsidian-second-brain:* хамт унтарна
for s in defuddle json-canvas obsidian-bases obsidian-cli obsidian-markdown; do
  [ -e "$s" ] && mv "$s" "$BK/moved-skills/"
done
[ -L diagram-design ] && mv diagram-design "$BK/moved-skills/"   # эвдэрсэн symlink (зорилт нь байхгүй)
ls "$BK/moved-skills"     # 7 зүйл
cd ~
```

fm v0.3-аас kepano-гийн skill-үүдийг fm-д хуулахаа больсон. Эдгээр 5 skill-ийг **албан ёсны** `obsidian@obsidian-skills` plugin өгнө — энэ алхмаас **өмнө** Claude Code-д суулга: `/plugin marketplace add kepano/obsidian-skills` → `/plugin install obsidian@obsidian-skills` (`/fm:setup`-ийн «албан ёсны plugin» алхам ч мөн санал болгоно). claude.ai «My Uploads» дахь хуучин `obsidian` хуулбарыг **itge.e өөрөө** вэбээс хасна.

**Буцаах:** `mv "$BK/moved-skills/"* ~/.claude/skills/`

## 5. Commands: OSB symlink → shim

```bash
cd ~/.claude/commands
# 5a. OSB руу заасан 48 symlink (одоо эвдэрсэн)
for f in *.md; do
  if [ -L "$f" ] && readlink "$f" | grep -q 'obsidian-second-brain/commands/'; then mv "$f" "$BK/moved-commands/"; fi
done
# 5b. shim-ээр солигдох өөрийн командууд (+ 01-project-admin .bak)
for f in obsidian-inbox.md obsidian-route.md track.md jirge.md sync.md 01-project-admin.md 01-project-admin.md.bak-*; do
  [ -e "$f" ] && mv "$f" "$BK/moved-commands/"
done
# 5c. shim суулгах (11 файл, энгийн файл - symlink биш)
for n in $SHIMS; do cp "$REPO/extras/aliases/$n.md" ~/.claude/commands/; done
ls ~/.claude/commands
cd ~
```

**Шалгах:** `ls "$BK/moved-commands" | wc -l` = 56 (48 symlink + 6 файл + 2 `.bak`). `~/.claude/commands`-д 11 shim + `relay.md`, `gcal-sync.md`, `notion-refs.md` = **14** файл. `find ~/.claude/commands -type l | wc -l` = 0.

Shim бүр 3 мөр: `description: хуучин нэр — 2026-11-05 хүртэл`, бие нь `fm:*` skill-ийг дуудна. 2026-11-05-нд shim-үүдийг устгана.

**Буцаах:**
```bash
for n in $SHIMS; do rm -f ~/.claude/commands/$n.md; done
mv "$BK/moved-commands/"* ~/.claude/commands/
```

## 6. Relay өгөгдлийг vault руу шилжүүлэх (`_system/fm/`) ба `~/.fmos/config.json`

`tools/relay/migrate_to_vault.py` нь `$REPO/relay/{registry,channels,discord,notion_links}.json` → `$VAULT/_system/fm/`, `$REPO/state/*.md` baton → `_system/fm/state/` гэж **хуулна** (эхийг хөндөхгүй), мөн `~/.fmos/config.json`-ийг (байхгүй бол) бичнэ. Хувийн (finance/tax/gold, `private: true`) baton хэзээ ч хуулагдахгүй. Default нь dry-run.

```bash
python3 "$REPO/tools/relay/migrate_to_vault.py" --vault "$VAULT" --device Mac --member itge.e --repo "$REPO"           # dry-run: төлөвлөгөөг унш
python3 "$REPO/tools/relay/migrate_to_vault.py" --vault "$VAULT" --device Mac --member itge.e --repo "$REPO" --apply
ls "$VAULT/_system/fm" "$VAULT/_system/fm/state"
cat ~/.fmos/config.json        # {"vault": "<VAULT>", "device": "Mac", "member": "itge.e"}
```

- Dry-run-д vault-д **аль хэдийн байгаа** файл гарвал `--force` бүү нэм — эхлээд ялгааг шалга.
- Сешн тоо таарч буйг шалга:
  ```bash
  python3 -c "import json,sys;a=json.load(open(sys.argv[1]))['sessions'];b=json.load(open(sys.argv[2]))['sessions'];print(len(a),len(b),set(a)-set(b))" "$REPO/relay/registry.json" "$VAULT/_system/fm/registry.json"
  ```
  Хоёр тоо тэнцүү, сүүлийн олонлог `set()` байна.
- `_system/fm/roles-draft.json` бол **ноорог** — `registry.json` руу itge.e хянасны дараа л нэгтгэнэ (`roles` + сешн бүрийн `role`).

**Буцаах:**
```bash
for f in registry.json channels.json discord.json notion_links.json state; do
  [ -e "$VAULT/_system/fm/$f" ] && mv "$VAULT/_system/fm/$f" "$BK/rolled-back/"
done
[ -f ~/.fmos/config.json ] && mv ~/.fmos/config.json "$BK/rolled-back/fmos-config.json"
[ -f "$BK/fmos-config.json" ] && cp -p "$BK/fmos-config.json" ~/.fmos/config.json
```

## 7. `~/.fmos/config.json`-ийг шалгах

6-р алхам бичсэн байх ёстой. Байхгүй (эсвэл `vault` буруу) бол:

```bash
mkdir -p ~/.fmos
python3 - "$VAULT" <<'EOF2'
import json, sys
from pathlib import Path
p = Path.home() / ".fmos" / "config.json"
if p.exists():
    print("байна, дарж бичсэнгүй:", p.read_text(encoding="utf-8"))
else:
    p.write_text(json.dumps({"vault": sys.argv[1], "device": "Mac", "member": "itge.e"},
                            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("бичлээ:", p)
EOF2
```

**Mac бол Discord бичигч биш** (PC бичнэ). Vault горимд dispatcher default-аар бичигч болдог тул Mac-ийн config-д `"writer": false` нэм — үгүй бол Discord мессеж бүр vault-ийн нэг файлд хоёр удаа бичигдэнэ:

```bash
python3 - <<'EOF3'
import json
from pathlib import Path
p = Path.home() / ".fmos" / "config.json"
c = json.loads(p.read_text(encoding="utf-8")); c["writer"] = False
p.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"); print(c)
EOF3
```

**Буцаах:** 6-р алхмын «Буцаах»-д багтсан.

## 8. Dispatcher LaunchAgent дахин эхлүүлэх

```bash
launchctl kickstart -k gui/$(id -u)/com.fmos.dispatcher
sleep 3
launchctl print gui/$(id -u)/com.fmos.dispatcher | grep -E "state =|pid ="
tail -n 20 ~/.fmos_dispatcher.log
```

`state = running` ба `pid = <тоо>` гарна. Лог дээр шинэ `Error`/`ENOENT` байх ёсгүй.

**Буцаах:** 6-р алхмыг буцаасны дараа ижил `kickstart -k` командыг дахин ажиллуул.

## 9. Шалгалт (шинэ сешнээр)

Vault дотроос **шинэ** Claude Code сешн нээ (`cd "$VAULT" && claude`), дараа нь:

| # | Шалгалт | Хүлээгдэх |
|---|---|---|
| 1 | Эхний context | `# Founder Matrix OS - vault context` ба `## BOOT.md` **нэг** удаа; «Skill root» мөр **байхгүй** |
| 2 | `/fm:` гэж бичих | `fm:save`, `fm:inbox`, `fm:role` … харагдана; `obsidian-second-brain:*` **байхгүй** |
| 3 | `/obsidian-save` | shim ажиллаж `fm:save` skill дуудагдана |
| 4 | MCP | `mcp__plugin_obsidian-second-brain_vault__*` tool **байхгүй** |
| 5 | Дүр | registry-д `roles` нэгтгэгдээгүй бол «дүргүй: /fm:role <slug>» гэж гарна (хэвийн) |
| 6 | Relay | `relay.py inbox` мөрүүд хэвээр гарна, Stop-д baton бичигдэнэ |

Терминалаас:

```bash
python3 "$REPO/extras/cutover_settings.py" --check                                   # exit 0
pgrep -fl "obsidian-mcp-server|load_vault_context" || echo "OSB процесс алга"   # хуучин сешнүүд хаагдсаны дараа
python3 "$REPO/plugins/fm/scripts/fm_lint.py" "$VAULT/_system/BOOT.md" --vault "$VAULT"   # "үр дүн цэвэр", exit 0
printf '{"session_id":"cutover-check","cwd":"%s"}' "$VAULT" | FM_VAULT="$VAULT" python3 "$REPO/plugins/fm/scripts/fm_context.py" | head -c 400; echo
ls ~/.claude/commands | wc -l                                                         # 14
```

Аль нэг нь бүтэлгүйтвэл **10-р алхмаар** бүрэн буцаа, эсвэл зөвхөн тэр алхмын «Буцаах»-ыг хий.

Амжилттай бол Discord `#03-sys-admin`-д: «Mac cut-over дууслаа — 1 өдөр ажиглаад PC». Дүрийн сешнүүдийг нэг нэгээр нь дахин эхлүүл: GTD → Area → Project → бусад.

## 10. Бүрэн буцаалт (урвуу дарааллаар)

```bash
# 8 → 6: өгөгдөл, config, dispatcher
for f in registry.json channels.json discord.json notion_links.json state; do
  [ -e "$VAULT/_system/fm/$f" ] && mv "$VAULT/_system/fm/$f" "$BK/rolled-back/"
done
[ -f ~/.fmos/config.json ] && mv ~/.fmos/config.json "$BK/rolled-back/fmos-config.json"
[ -f "$BK/fmos-config.json" ] && cp -p "$BK/fmos-config.json" ~/.fmos/config.json
launchctl kickstart -k gui/$(id -u)/com.fmos.dispatcher
# 5: commands
for n in $SHIMS; do rm -f ~/.claude/commands/$n.md; done
mv "$BK/moved-commands/"* ~/.claude/commands/
# 4: skills
mv "$BK/moved-skills/"* ~/.claude/skills/
# 3: settings
cp -p "$BK/claude/settings.json" ~/.claude/settings.json
# 2: plugin
claude plugin uninstall fm@founder-matrix
claude plugin marketplace remove founder-matrix
cp -p "$BK/claude/plugins/"*.json ~/.claude/plugins/
```

**Буцаалтыг шалгах:**
```bash
shasum -a 256 ~/.claude/settings.json | diff - <(head -1 "$BK/sha256-before.txt") && echo "settings ижил"
diff <(ls -A "$BK/claude/commands") <(ls -A ~/.claude/commands) && echo "commands ижил"
diff <(ls -A "$BK/claude/skills") <(ls -A ~/.claude/skills) && echo "skills ижил"
ls ~/.claude/skills/obsidian-second-brain/hooks/load_vault_context.py
```

`_system/BOOT.md` ба `_system/fm/roles-draft.json` хоргүй (юу ч уншдаггүй) — буцаахад үлдээж болно.

## 11. Дараа нь

- **2026-11-05:** `for n in $SHIMS; do rm ~/.claude/commands/$n.md; done`; `AI_FIRST_SKIP_CHARSET`-ийг `settings.json`-оос хас.
- **30 хоногийн дараа**, бүх зүйл тогтвортой бол `$BK`-г устга.
- `obsidian-dna` skill, `fmos-harvester-mac` task-ийн `/obsidian-*` дурдлагууд — тусдаа task.
