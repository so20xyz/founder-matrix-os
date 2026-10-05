#!/usr/bin/env bash
# =============================================================================
#  founder-matrix-os — git ТҮҮХЭЭС хувийн өгөгдлийг цэвэрлэх (history purge)
#
#  !!!  DO NOT RUN without itge.e + PC coordination  !!!
#  !!!  itge.e болон PC-тэй тохиролцохгүйгээр БҮҮ ажиллуул  !!!
#
#  Энэ скрипт GitHub дээрх бүх commit-ийг дахин бичээд force-push хийнэ.
#  Буцаах цорын ганц арга нь 1-р алхмын backup mirror.
#  Dry run (2026-10-05, throwaway mirror): 390 -> 62 commit, pack 14.4 MiB -> 0.37 MiB,
#  plugins/fm, tools/relay, tools/figma (html2fig-гүй), README HEAD-д хэвээр,
#  tests/test_hooks.py 39/39 passed.
#
#  Шаардлага: git, python3, git-filter-repo (`brew install git-filter-repo`
#  эсвэл `pip3 install --user git-filter-repo`). macOS bash 3.2-д ажиллана.
#
#  Ажиллуулах:   CONFIRM=I-COORDINATED-WITH-PC OLD_EMAIL='<хуучин author email>' \
#                bash extras/history-cleanup.sh
#  Шинэ repo руу (санал болгох — GitHub хуучин SHA-г cache-лдаг):
#                NEW_REPO_URL=https://github.com/<owner>/<new-repo>.git ...
# =============================================================================
set -euo pipefail

# ---- 0. Урьдчилсан нөхцөл (ГАРААР шалга, бүгд ✓ болсон үед л ажиллуул) ---------
cat <<'PRE'
[0] Урьдчилсан нөхцөл — бүгдийг гараар шалгасан уу?
  1. fm-v02 (болон бусад хэрэгтэй branch) main руу merge хийгдэж GitHub-д push болсон.
     Rewrite-ийн дараа хуучин суурьтай branch-ууд rebase хийх шаардлагатай болно.
  2. Mac БОЛОН PC дээр relay hook-ууд ИДЭВХГҮЙ (~/.claude/settings.json-ийн
     relay.py inbox/baton/status hook-ууд). Тэд `git pull --rebase` + `git push`
     хийдэг тул хуучин түүхийг буцааж push хийж болзошгүй.
     Mac: launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.fmos.dispatcher.plist
     PC : Task Scheduler / dispatcher процессыг зогсоо.
  3. Legacy өгөгдөл (state/, relay/*.json|*.md, claude/settings.json,
     claude/launch.json, tools/notion/nt.config.json, tools/figma/html2fig/, *.tsv)
     vault-ийн _system/fm/ руу шилжиж, мөн repo-гийн гадна backup хийгдсэн.
     Эдгээр нь tracked файл тул `git reset --hard` хийхэд working tree-ээс УСТНА.
  4. Хоёр машин дээр push хийгээгүй commit байхгүй (`git status`, `git log origin/main..`).
PRE

if [ "${CONFIRM:-}" != "I-COORDINATED-WITH-PC" ]; then
  echo "CONFIRM=I-COORDINATED-WITH-PC тохируулаагүй тул зогслоо. (DO NOT RUN without itge.e + PC coordination)"
  exit 1
fi
command -v git-filter-repo >/dev/null 2>&1 || { echo "git-filter-repo суулгаагүй байна."; exit 1; }
: "${OLD_EMAIL:?OLD_EMAIL (commit-уудын хуучин author email) заавал өг}"

SRC_URL="${SRC_URL:-https://github.com/rollingbd/founder-matrix-os.git}"
PUSH_URL="${NEW_REPO_URL:-$SRC_URL}"
NEW_IDENT="${NEW_IDENT:-itge.e <rollingbd@users.noreply.github.com>}"
MAC_USER="${MAC_USER:-$(id -un)}"   # itge.e-ийн Mac дээр ажиллуулбал өөрийн нэр нь
DATE="$(date +%Y-%m-%d)"
BACKUP="$HOME/Backups/founder-matrix-os-pre-cleanup-$DATE.git"
WORK="$HOME/Backups/fmos-cleanup-$DATE"

# ---- 1. Backup mirror (repo-гийн бүх ref, анхны хэвээр) -----------------------
mkdir -p "$HOME/Backups"
if [ -e "$BACKUP" ]; then echo "Backup аль хэдийн байна: $BACKUP — устгах/нэр солихгүйгээр үргэлжлэхгүй."; exit 1; fi
git clone --mirror "$SRC_URL" "$BACKUP"
echo "[1] backup: $BACKUP ($(git --git-dir="$BACKUP" rev-list --all --count) commits)"

# ---- 2. Fresh mirror (filter-repo fresh clone шаарддаг) -------------------------
rm -rf "$WORK"; mkdir -p "$WORK"
git clone --no-local --mirror "$BACKUP" "$WORK/repo.git"
cd "$WORK/repo.git"
git update-ref -d refs/stash 2>/dev/null || true
BEFORE_COMMITS="$(git rev-list --all --count)"
git gc -q --prune=now
BEFORE_SIZE="$(git count-objects -vH | sed -n 's/^size-pack: //p')"

# ---- 3. Purge жагсаалт + replace-text (зөвхөн ерөнхий regex — хувийн утга агуулахгүй)
cat > "$WORK/purge-paths.txt" <<'EOF'
state/
relay/
vault/
claude/settings.json
claude/launch.json
claude/agents/creative-director.md
tools/figma/html2fig/
tools/figma/pouch_draw.py
tools/notion/nt.config.json
glob:*.tsv
EOF
# Тэмдэглэл: tools/relay/relay.py дахь `D:/My Drive/...` (Google Drive-ийн default mount)
# санаатайгаар солигдоогүй — амьд код. fm-v02 ~/.fmos/config.json руу шилжүүлнэ.
cat > "$WORK/replacements.txt" <<'EOF'
regex:DESKTOP-[A-Z0-9]{7}==>PC-HOST
regex:[A-Za-z0-9_-]+-MacBook-(Air|Pro)(-[0-9]+)?(\.local)?==>MAC-HOST
regex:[A-Za-z0-9._%+-]+@gmail\.com==>user@example.com
regex:[Dd]:[/\\]Vaults[/\\]Founder\.Matrix==><OLD-VAULT>
regex:[A-Za-z]:\\My Drive\\Second Brain 2\.0==><VAULT>
regex:[Dd]:([/\\])CodeBase==>~\1CodeBase
regex:(?<![0-9])1[0-9]{17,19}(?![0-9])==>DISCORD_ID
regex:(?<![0-9a-f-])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f-])==>NOTION_PAGE_ID
regex:(ROOT_PAGE = ')[0-9a-f]{32}(')==>\1YOUR_NOTION_ROOT_PAGE_ID\2
regex:(VAULT = ")[0-9a-f]{16}(")==>\1YOUR_VAULT_ID\2
regex:`[A-Za-z0-9]{22}`==>`FIGMA_FILE_KEY`
EOF
# Mac хэрэглэгчийн home зам (`/Users/<MAC_USER>/...` -> `$HOME/...`). Зөвхөн энэ хэрэглэгч —
# docs дахь `/Users/you/...` жишээ, CI-ийн `/Users/...\b` regex хөндөгдөхгүй.
printf 'regex:/Users/%s(?=[/"'"'"'`\\s]|$)==>$HOME\n' "$MAC_USER" >> "$WORK/replacements.txt"
printf '%s <%s>\n' "$NEW_IDENT" "$OLD_EMAIL" > "$WORK/mailmap.txt"

# ---- 4. Rewrite ------------------------------------------------------------------
git filter-repo \
  --invert-paths --paths-from-file "$WORK/purge-paths.txt" \
  --replace-text "$WORK/replacements.txt" \
  --mailmap "$WORK/mailmap.txt"
git gc -q --aggressive --prune=now
rm -f "$WORK/mailmap.txt"
AFTER_COMMITS="$(git rev-list --all --count)"
AFTER_SIZE="$(git count-objects -vH | sed -n 's/^size-pack: //p')"

# ---- 5. Шалгалт: бүх түүхийг дахин скан ------------------------------------------
echo "[5] re-scan (бүх commit)…"
FAIL=0
REVS="$(git rev-list --all)"
scan() { # $1 = label, $2 = ERE, $3 = зөвшөөрөгдсөн мөрийн ERE (хоосон бол юу ч биш)
  local hits
  hits="$(echo "$REVS" | xargs git grep -I -h -o -E "$2" 2>/dev/null | sort -u || true)"
  if [ -n "$3" ] && [ -n "$hits" ]; then hits="$(echo "$hits" | grep -v -E "$3" || true)"; fi
  if [ -n "$hits" ]; then echo "  !! $1:"; echo "$hits" | head -5 | sed 's/^/     /'; FAIL=1; else echo "  ok $1"; fi
}
scan "mac home path"      "/Users/${MAC_USER}([/\"'\`[:space:]]|\$)" ''
scan "windows D: path"    '[Dd]:[/\\][A-Za-z]+' '^D:/My$|^[Dd]:\\[dn]$'
scan "hostnames"          'DESKTOP-[A-Z0-9]{7}|-MacBook-(Air|Pro)' ''
scan "gmail"              '[A-Za-z0-9._%+-]+@gmail\.com' ''
scan "discord snowflake"  '(^|[^0-9])1[0-9]{17,19}([^0-9]|$)' ''
scan "notion 32-hex"      '(^|[^0-9a-fA-F])[0-9a-f]{32}([^0-9a-fA-F]|$)' ''
for p in state relay vault tools/figma/html2fig tools/notion/nt.config.json claude/settings.json claude/launch.json; do
  if git log --all --format=%H -- "$p" | grep -q .; then echo "  !! path still in history: $p"; FAIL=1; fi
done
if git log --all --format='%ae%n%ce' | grep -qiF "$OLD_EMAIL"; then echo "  !! OLD_EMAIL still in commit metadata"; FAIL=1; fi
for p in plugins/fm tools/relay plugins/fm/tools/figma README.md; do
  git cat-file -e "main:$p" 2>/dev/null && echo "  ok HEAD has $p" || { echo "  !! HEAD missing $p"; FAIL=1; }
done
echo "[5] commits: $BEFORE_COMMITS -> $AFTER_COMMITS   pack: $BEFORE_SIZE -> $AFTER_SIZE"
[ "$FAIL" = 0 ] || { echo "Скан амжилтгүй — push хийхгүй. $WORK/repo.git-ийг шалга."; exit 1; }

# ---- 6. Push (эцсийн баталгаажуулалт) --------------------------------------------
echo "[6] Push хийх газар: $PUSH_URL"
printf 'Force-push хийх үү? "PUSH" гэж бич: '; read -r ans
[ "$ans" = "PUSH" ] || { echo "Push хийгээгүй. Rewrite хийсэн repo: $WORK/repo.git"; exit 0; }
git remote remove origin 2>/dev/null || true
git remote add origin "$PUSH_URL"
git push --force origin 'refs/heads/*:refs/heads/*'
git push --force --tags origin
echo "[6] Push боллоо. GitHub дээр зөвхөн rewrite-д байхгүй хуучин branch-ууд үлдсэн эсэхийг шалгаж, устга."

# ---- 7. Машин бүр дээр (Mac + PC) — ГАРААР ---------------------------------------
cat <<'POST'
[7] Mac болон PC дээрх clone бүрт (нэг нэгээр, hook-ууд унтраалттай байхад):
  1. Legacy өгөгдлөө repo-гийн гадна хуулж backup хий (state/, relay/, claude/settings.json,
     claude/launch.json, tools/notion/nt.config.json, tools/figma/html2fig/, *.tsv) —
     reset хийхэд tracked байсан эдгээр файл устна. Vault-ийн _system/fm/ руу шилжсэн эсэхийг шалга.
  2. git stash list — хуучин autostash-ууд хуучин түүх дээр суурилсан; хэрэгтэйг нь гаргаад хадгал,
     дараа нь: git stash clear
  3. git fetch origin
     git checkout main && git reset --hard origin/main
     (NEW_REPO_URL ашигласан бол эхлээд: git remote set-url origin <шинэ URL>)
  4. Бусад branch/worktree (жишээ fm-v02): шинэ origin/main дээр суурилуулж дахин үүсгэ
     (git worktree remove ...; git branch -D fm-v02; git worktree add ... origin/main)
     эсвэл: git rebase --onto origin/main <хуучин-суурь> <branch>
  5. git reflog expire --expire=now --all && git gc --prune=now   (хуучин объектыг локалаас арилгах)
  6. Hook-ууд + dispatcher-ийг дахин асаа (одоо зөвхөн vault-ийн _system/fm/ руу бичнэ).
  7. Хуучин clone-оос (хуучин түүхтэй) хэзээ ч `git push` бүү хий.
GitHub: хуучин commit-ууд SHA-аар cache-д үлдэж болно → оюутнуудад эрх өгөхөөс өмнө
шинэ repo (NEW_REPO_URL) ашиглах эсвэл GitHub Support-оор cached view цэвэрлүүлэх.
POST
