#!/usr/bin/env python3
"""fm_goom_pull — Goomnet-ийн vault_change outbox-ийг уншиж vault-д хэрэгжүүлнэ (PC дээр, dry-run анхдагч).

  python fm_goom_pull.py <vault>            # хүлээгдэж буй хүсэлтүүдийг харуулна, юу ч бичихгүй
  python fm_goom_pull.py <vault> --apply    # хэрэгжүүлээд Goomnet-д applied гэж тэмдэглэнэ

Төрлүүд:
  capture  → 01-GTD/Inbox/YYYY-MM-DD HHMM - <гарчиг>.md  (type: inbox, source: goomnet)
  status   → task-ийн frontmatter-ийн `status:` мөрийг л солино + «## Өөрчлөлтийн түүх»-д
             `| HH:MM | Goomnet-оос төлөв: X → Y | Goomnet |` мөр нэмнэ (append-only)
  decision → 04-Resources/Atomic/decisions/YYYY-MM-DD - <гарчиг>.md (type: session-decision),
             дараа нь board-ийн node-д data.atom_path-ийг буцааж бичнэ

Idempotent: capture/decision note-д `goomnet_change: <id>` бичигдэнэ — дахин ажиллахад шинэ файл
үүсгэхгүй; status нь төлөв аль хэдийн Y, түүхэнд мөр нь байвал юу ч хийхгүй.
🔒 private зам руу хэзээ ч бичихгүй (applied + error). ~/.fmos/goom.json — fm_goom_sync-тэй ижил;
token хэвлэхгүй. Stdlib.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm_goom_sync as gs  # noqa: E402

UB = timezone(timedelta(hours=8))
INBOX = "01-GTD/Inbox"
DECISIONS = "04-Resources/Atomic/decisions"
HISTORY = "## Өөрчлөлтийн түүх"
_BAD = re.compile(r'[/\\:*?"<>|\r\n\t]')
_TRUE = ("true", "yes", "on", "1")
# GTD statuses the vault accepts (mirrors goomnet change.AllowedStatuses).
STATUSES = frozenset({"inbox", "next-action", "in-progress", "waiting", "someday", "completed", "cancelled"})


class RejectedError(Exception):
    """A request the PC refuses to apply; it is closed on Goomnet with the reason, not retried."""


class PrivatePathError(RejectedError):
    pass


class BadStatusError(RejectedError):
    pass


# ---------- HTTP ----------

class Client:
    """Goomnet API; token stays inside, never printed."""

    def __init__(self, url, token):
        self.url, self._token = url.rstrip("/"), token

    def call(self, method, path, body=None):
        req = urllib.request.Request(
            self.url + path,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
            method=method,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._token},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}


def _http_status(err):
    return getattr(err, "code", None)


# ---------- helpers ----------

def safe_title(text, limit=60):
    """First non-empty line, no filename-hostile characters, at most `limit` characters."""
    first = next((ln.strip() for ln in str(text or "").splitlines() if ln.strip()), "")
    t = re.sub(r"\s+", " ", _BAD.sub(" ", first)).strip().strip(".")
    if len(t) > limit:
        t = t[:limit].rstrip()
    return t or "Goomnet"


def _yaml_str(s):
    return json.dumps(str(s), ensure_ascii=False)


def _is_private_rel(rel):
    low = rel.lower()
    return "finances/private" in low or "🔒" in rel


def _resolve(vault, rel):
    rel = unicodedata.normalize("NFC", str(rel or "").replace("\\", "/")).lstrip("/")
    if not rel or _is_private_rel(rel):
        raise PrivatePathError(f"private or empty path: {rel!r}")
    p = (vault / rel).resolve()
    if vault.resolve() not in p.parents:
        raise PrivatePathError(f"path outside vault: {rel!r}")
    return p, rel


def _note_is_private(text, path):
    raw, _body = gs._split(text)
    fm = {}
    if raw is not None:
        try:
            fm = gs._parse_fields(raw.splitlines())
        except gs.YamlError:
            fm = {}
    priv = fm.get("private")
    title = fm.get("title") if isinstance(fm.get("title"), str) else path.stem
    return priv is True or str(priv if priv is not None else "").strip().lower() in _TRUE or "🔒" in str(title)


def _read_note(path):
    """Note text with CR removed, so CRLF files (Windows editors, Drive) match LF-based checks."""
    return path.read_text(encoding="utf-8").replace("\r", "")


def _find_by_change(folder, change_id):
    if not folder.is_dir():
        return None
    marker = f"goomnet_change: {change_id}\n"
    for f in sorted(folder.glob("*.md")):
        try:
            if marker in _read_note(f):
                return f
        except (OSError, UnicodeDecodeError):
            continue
    return None


def _free_path(folder, stem):
    p = folder / f"{stem}.md"
    n = 2
    while p.exists():
        p = folder / f"{stem} ({n}).md"
        n += 1
    return p


def _write(path, text):
    """Temp file in the same folder, then os.replace: a crash leaves the old note or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------- capture ----------

def plan_capture(vault, change, now):
    cid = change["change_id"]
    text = str((change.get("payload") or {}).get("text") or "").strip()
    folder = vault / INBOX
    existing = _find_by_change(folder, cid)
    if existing:
        return existing, None
    created = now.strftime("%Y-%m-%d %H:%M")
    path = _free_path(folder, f"{now.strftime('%Y-%m-%d %H%M')} - {safe_title(text)}")
    body = (
        "---\n"
        "type: inbox\n"
        "source: goomnet\n"
        f"created: {created}\n"
        f"goomnet_change: {cid}\n"
        "---\n\n"
        f"{text}\n"
    )
    return path, body


# ---------- status ----------

_STATUS_RE = re.compile(r"^status:[ \t]*(.*?)[ \t]*$", re.M)


def edit_status(text, target, now):
    """Returns new text (or None when nothing changes). Touches only the frontmatter `status:` line and
    appends one history row."""
    if not text.startswith("---\n"):
        raise ValueError("note has no frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    fm, rest = text[:end + 1], text[end + 1:]
    m = _STATUS_RE.search(fm)
    current = m.group(1).strip().strip('"\'') if m else ""
    row_text = f"Goomnet-оос төлөв: {current or '—'} → {target}"
    already_row = re.search(r"\|\s*Goomnet-оос төлөв: [^|]*→ " + re.escape(target) + r"\s*\|", rest) is not None
    if current == target and already_row:
        return None
    if current != target:
        if m:
            fm = fm[:m.start()] + f"status: {target}" + fm[m.end():]
        else:
            fm = fm + f"status: {target}\n"
    row = f"| {now.strftime('%H:%M')} | {row_text} | Goomnet |"
    lines = rest.split("\n")
    idx = next((i for i, ln in enumerate(lines) if ln.strip() == HISTORY), None)
    if idx is None:
        tail = rest.rstrip("\n")
        rest = tail + f"\n\n{HISTORY}\n\n| Цаг | Юу | Хаана |\n|---|---|---|\n{row}\n"
    else:
        insert = idx + 1
        j = idx + 1
        while j < len(lines) and not lines[j].startswith("## "):
            if lines[j].strip().startswith("|"):
                insert = j + 1
            j += 1
        if insert == idx + 1:
            lines[insert:insert] = ["", "| Цаг | Юу | Хаана |", "|---|---|---|", row]
        else:
            lines.insert(insert, row)
        rest = "\n".join(lines)
    return fm + rest


def plan_status(vault, change, now):
    p = change.get("payload") or {}
    target = str(p.get("status") or "").strip()
    if not target or "\n" in target:
        raise ValueError("status missing")
    if target not in STATUSES:
        raise BadStatusError(f"status not allowed: {target!r}")
    path, _rel = _resolve(vault, p.get("source_path"))
    if not path.is_file():
        raise FileNotFoundError(f"task not found: {_rel}")
    text = _read_note(path)
    if _note_is_private(text, path):
        raise PrivatePathError(f"private note: {_rel}")
    return path, edit_status(text, target, now)


# ---------- decision ----------

def plan_decision(vault, change, now):
    cid = change["change_id"]
    p = change.get("payload") or {}
    folder = vault / DECISIONS
    existing = _find_by_change(folder, cid)
    if existing:
        return existing, None
    title = safe_title(p.get("title") or p.get("text"))
    date = now.strftime("%Y-%m-%d")
    path = _free_path(folder, f"{date} - {title}")
    board_id, node_id = p.get("board_id"), p.get("node_id")
    board_title = str(p.get("board_title") or "").strip()
    lines = [
        "---",
        "type: session-decision",
        f"date: {date}",
        "decidedby: me",
    ]
    if p.get("meeting_task"):
        lines.append(f"meeting: {_yaml_str('[[' + str(p['meeting_task']).strip() + ']]')}")
    lines += [
        f"board: {_yaml_str(f'Goomnet board #{board_id}' + (f' — {board_title}' if board_title else ''))}",
        f"board_id: {board_id}",
        f"board_node: {_yaml_str(node_id)}",
        "source: goomnet",
        f"goomnet_change: {cid}",
        "ai-first: true",
        "---",
        "",
        f"# {str(p.get('title') or title).strip()}",
        "",
        str(p.get("text") or "").strip(),
        "",
        "## For future agent",
        "",
        f"- Энэ шийдвэрийг itge.e Goomnet-ийн хурлын өрөөнд (board #{board_id}, node `{node_id}`) батлав.",
        "- Дахин хэлэлцэхгүй; өөрчлөх бол шинэ шийдвэрийн атом үүсгэж энэ атомыг холбоно.",
        "",
    ]
    return path, "\n".join(lines)


def write_back_atom_path(client, board_id, node_id, rel):
    """GET board → set node data.atom_path → PUT with version; one retry on 409."""
    for attempt in range(2):
        board = client.call("GET", f"/api/web/private/vault/boards/{board_id}")
        doc, version = board.get("doc") or {}, board.get("version")
        found = False
        for n in doc.get("nodes") or []:
            if n.get("id") == node_id:
                data = dict(n.get("data") or {})
                data["atom_path"] = rel
                data.pop("atom_pending", None)
                n["data"] = data
                found = True
        if not found:
            raise LookupError(f"node {node_id} not on board {board_id}")
        try:
            client.call("PUT", f"/api/web/private/vault/boards/{board_id}", {"doc": doc, "version": version})
            return
        except urllib.error.HTTPError as e:
            if _http_status(e) == 409 and attempt == 0:
                continue
            raise


# ---------- run ----------

PLANNERS = {"capture": plan_capture, "status": plan_status, "decision": plan_decision}


def process(vault, changes, apply, client=None, now=None):
    """Returns a list of result dicts. Writes and marks applied only when apply=True."""
    vault = Path(vault)
    now = now or datetime.now(UB)
    results = []
    for ch in sorted(changes, key=lambda c: c.get("change_id", 0)):
        cid, kind = ch.get("change_id"), ch.get("kind")
        res = {"change_id": cid, "kind": kind}
        try:
            planner = PLANNERS.get(kind)
            if planner is None:
                raise ValueError(f"unknown kind {kind!r}")
            path, text = planner(vault, ch, now)
            rel = path.relative_to(vault).as_posix()
            res.update(path=rel, action="noop" if text is None else "write")
            if apply:
                if text is not None:
                    _write(path, text)
                if kind == "decision" and client is not None:
                    p = ch.get("payload") or {}
                    try:
                        write_back_atom_path(client, p.get("board_id"), p.get("node_id"), rel)
                    except Exception as e:  # atom is written; the board just keeps ⏳
                        res["warning"] = f"board write-back failed: {type(e).__name__}: {e}"
                if client is not None:
                    _close(client, cid, res)
        except RejectedError as e:
            res.update(action="rejected", error=str(e))
            if apply and client is not None:
                _close(client, cid, res, error=str(e))
        except Exception as e:  # left pending; next run retries
            res.update(action="error", error=f"{type(e).__name__}: {e}")
        results.append(res)
    return results


def _close(client, cid, res, error=None):
    """Mark a change applied on Goomnet. A failure is recorded on the result and never stops the batch;
    the note is already written, so the next run sees it as noop and retries only the close."""
    body = {"error": error} if error else {}
    try:
        client.call("POST", f"/api/web/private/vault/changes/{cid}/applied", body)
        res["applied"] = True
    except Exception as e:
        res.update(action="error", error=f"mark applied failed: {type(e).__name__}: {e}")


def main(argv=None):
    getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Goomnet vault_change → vault (dry-run unless --apply).")
    ap.add_argument("vault")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    vault = Path(a.vault)
    if not vault.is_dir():
        print(f"vault not found: {vault}", file=sys.stderr)
        return 2
    try:
        url, token, ws = gs._load_config()
    except gs.SystemExit_ as e:
        print(str(e), file=sys.stderr)
        return 2
    client = Client(url, token)
    try:
        changes = client.call("GET", f"/api/web/private/vault/changes?workspace_id={ws}&pending=1").get("changes") or []
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"Goomnet unreachable: {type(e).__name__}", file=sys.stderr)
        return 1
    results = process(vault, changes, a.apply, client if a.apply else None)
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    print(json.dumps({"mode": "apply" if a.apply else "dry-run", "pending": len(changes),
                      "errors": sum(1 for r in results if r.get("action") == "error")}, ensure_ascii=False))
    return 1 if any(r.get("action") == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
