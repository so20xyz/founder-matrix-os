#!/bin/bash
# Screenshot -> vault-ийн 01-GTD/Inbox. AL CH app-aas ajillana (Messages g.m native app-uud) -
# browser extension-ees yalgaatai ni macOS-iin screencapture tab bish buh delgetsiig zurna.
# Zurag avsny daraa "Claude-d yuu hiilgeh ve?" gej asууna -> notod bichigdene.
#
# Holboh: Shortcuts.app -> "Run Shell Script" -> ene file-iig duudaad keyboard shortcut onoo (jishee Ctrl+Cmd+Opt+V).
# Ⓘ macOS Sonoma+ deer Screen Recording zovshoorol shaardana (System Settings > Privacy > Screen Recording).

set -e
# Vault: env FM_VAULT, эс бөгөөс ~/.fmos/config.json-ийн "vault" (fm /fm:setup үүсгэнэ).
VAULT="${FM_VAULT:-$(python3 -c 'import json,os,sys;print(json.load(open(os.path.expanduser(os.environ.get("FMOS_CONFIG","~/.fmos/config.json")),encoding="utf-8")).get("vault",""))' 2>/dev/null || true)}"
if [ -z "$VAULT" ] || [ ! -d "$VAULT" ]; then
  osascript -e 'display notification "Vault олдсонгүй: ~/.fmos/config.json эсвэл FM_VAULT" with title "fm"' 2>/dev/null || true
  echo "Vault олдсонгүй: ~/.fmos/config.json-д \"vault\" бич эсвэл FM_VAULT тавь" >&2
  exit 1
fi
INBOX="$VAULT/01-GTD/Inbox"
# shiljiltiin hamgaalalt: shine zam baihgui ch odoogiin 00-GTD/Inbox / huuchin 00-Inbox baival tuuniig
[ ! -d "$INBOX" ] && [ -d "$VAULT/00-GTD/Inbox" ] && INBOX="$VAULT/00-GTD/Inbox"
[ ! -d "$INBOX" ] && [ -d "$VAULT/02-GTD/inbox" ] && INBOX="$VAULT/02-GTD/inbox"
[ ! -d "$INBOX" ] && [ -d "$VAULT/00-Inbox" ] && INBOX="$VAULT/00-Inbox"
ATT="$VAULT/_system/attachments"
mkdir -p "$ATT"
TS="$(date +%Y-%m-%d-%H%M%S)"
PNG="screenshot - $TS.png"

# Interactive: hereglegch muj songono (space daraad tsonh songo bolno). Esc darwal file uusehgui.
/usr/sbin/screencapture -i "$ATT/$PNG"
[ -f "$ATT/$PNG" ] || exit 0

# Claude-d yuu hiilgeh ve? (Cancel darwal hooson)
TASK="$(osascript -e 'try' -e 'text returned of (display dialog "Claude-д юу хийлгэх вэ? (хоосон орхиж болно)" default answer "" with title "Screenshot -> Inbox" buttons {"Cancel","Save"} default button "Save")' -e 'on error' -e 'return ""' -e 'end try' 2>/dev/null || echo "")"

NOTE="$INBOX/capture - $TS.md"
DAY="$(date +%Y-%m-%d)"
HM="$(date +%H:%M)"
{
cat <<EOF
---
date: $DAY
type: reference
status: draft
tags:
  - reference
  - inbox
  - screenshot
reftype: screenshot
source: screenshot
needs-claude: true
ai-first: true
---

## For future agent

Screenshot capture $DAY $HM - screenshot-to-inbox hotkey-eer avav (al ch app-aas). Doorh zurgiig unshaad "Claude-d daalgavar"-ыг guitsetge, daraa ni zov haltas ruu bairluul.

![[$PNG]]

## 🤖 Claude-d daalgavar

EOF
printf '%s\n' "$TASK"
cat <<'EOF'

## ✍️ Minii temdeglel

EOF
} > "$NOTE"

osascript -e "display notification \"$PNG\" with title \"Saved to Inbox\"" 2>/dev/null || true
