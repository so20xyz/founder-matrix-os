#!/bin/bash
# Finder-d songoson file(uud)-iig vault-ийн 02-GTD/inbox ruu zoono (Downloads-oos gol tolov).
# Songolt baihgui bol Downloads-iin hamgiin shine zuiliig zoono.
# Holboh: Shortcuts.app -> "Run Shell Script" -> ene file -> keyboard shortcut onoo.
# NOTE: set -e ashiglahgui (nohtsolt file uildluud).

# Vault: env FM_VAULT, эс бөгөөс ~/.fmos/config.json-ийн "vault" (fm /fm:setup үүсгэнэ).
VAULT="${FM_VAULT:-$(python3 -c 'import json,os,sys;print(json.load(open(os.path.expanduser(os.environ.get("FMOS_CONFIG","~/.fmos/config.json")),encoding="utf-8")).get("vault",""))' 2>/dev/null || true)}"
if [ -z "$VAULT" ] || [ ! -d "$VAULT" ]; then
  osascript -e 'display notification "Vault олдсонгүй: ~/.fmos/config.json эсвэл FM_VAULT" with title "fm"' 2>/dev/null || true
  echo "Vault олдсонгүй: ~/.fmos/config.json-д \"vault\" бич эсвэл FM_VAULT тавь" >&2
  exit 1
fi
INBOX="$VAULT/02-GTD/inbox"
# shiljiltiin hamgaalalt: shine zam baihgui ch huuchin 00-Inbox baival tuuniig
[ ! -d "$INBOX" ] && [ -d "$VAULT/00-Inbox" ] && INBOX="$VAULT/00-Inbox"
DL="${DOWNLOADS_DIR:-${HOME}/Downloads}"
mkdir -p "$INBOX"

# Finder-iin songoltiig POSIX zamaar av (mor bur = neg file)
SEL="$(osascript <<'AS' 2>/dev/null
set out to ""
tell application "Finder"
  set sel to selection
  repeat with i in sel
    set out to out & (POSIX path of (i as alias)) & linefeed
  end repeat
end tell
return out
AS
)"

moved=0
last=""
move_one() {
  local f="$1"
  f="${f%/}"
  if [ ! -e "$f" ]; then return 0; fi
  local base dest
  base="$(basename "$f")"
  dest="$INBOX/$base"
  if [ -e "$dest" ]; then dest="$INBOX/$(date +%H%M%S)-$base"; fi
  if mv "$f" "$dest"; then moved=$((moved + 1)); last="$base"; fi
}

if [ -n "$(printf '%s' "$SEL" | tr -d '[:space:]')" ]; then
  while IFS= read -r f; do
    [ -n "$f" ] && move_one "$f"
  done <<EOF
$SEL
EOF
else
  newest="$(ls -t "$DL" 2>/dev/null | head -1)"
  [ -n "$newest" ] && move_one "$DL/$newest"
fi

if [ "$moved" -gt 0 ]; then
  msg="$moved файл 02-GTD/inbox руу зөөв"
  [ "$moved" -eq 1 ] && msg="$last -> 02-GTD/inbox"
  osascript -e "display notification \"$msg\" with title \"Move to Inbox\"" 2>/dev/null || true
else
  osascript -e 'display notification "Файл сонгоогүй / олдсонгүй" with title "Move to Inbox"' 2>/dev/null || true
fi
