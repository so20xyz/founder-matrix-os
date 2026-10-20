#!/usr/bin/env python3
"""Regenerate references/catalog.md from the upstream Awesome-Auto-Research-Tools README.

Upstream: https://github.com/handsome-rich/Awesome-Auto-Research-Tools (CC0-1.0)

Usage (stdlib only; Windows: `py -3`, macOS/Linux: `python3`):

    python3 refresh_catalog.py                      # fetch README + stars, write ../references/catalog.md
    python3 refresh_catalog.py --readme FILE        # parse a local README copy instead of fetching
    python3 refresh_catalog.py --no-stars           # skip star / marketplace lookups (stars = "?")
    python3 refresh_catalog.py --out FILE --date YYYY-MM-DD

Fetch order: `gh api` (authenticated) first, then the public GitHub API / raw.githubusercontent.com.
Output is deterministic for the same inputs (README, stars, sha, date) and the file is rewritten
only when its content changes, so re-running is idempotent.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

UPSTREAM_REPO = "handsome-rich/Awesome-Auto-Research-Tools"
UPSTREAM_URL = "https://github.com/" + UPSTREAM_REPO
RAW_URL = "https://raw.githubusercontent.com/%s/HEAD/README.md" % UPSTREAM_REPO
HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "references" / "catalog.md"

# Short stage tags per upstream section (used by the skill to filter by research stage).
SECTION_STAGES = {
    "Autonomous Research Systems": "end-to-end: idea -> experiment -> paper",
    "Deep Research & Literature Synthesis": "literature review, web/deep research, cited reports",
    "Research Implementation & Experimentation": "code, reproduce papers, run/optimize experiments",
    "Academic Writing & Communication": "summarize, polish, figures, posters, reviews/rebuttals",
    "Research Skills & Plugin Collections": "skill packs for coding agents (Claude Code, Codex, ...)",
    "Awesome Lists & Surveys": "further discovery (other curated lists)",
}

# "Claude Code compatible": the Tools/LLM APIs cell names Claude Code, a Claude Skill, Agent Skills or MCP.
# A bare "Anthropic Claude" API mention does not count.
CLAUDE_RE = re.compile(r"claude[ -]code|claude skills?|agent skills?|\bmcp\b", re.I)
ROW_RE = re.compile(r"^\|\s*\[")
LINK_CELL_RE = re.compile(r"^\s*\[([^\]]+)\]\((https?://[^)\s]+)\)")
GH_REPO_RE = re.compile(r"https?://github\.com/([^/\s]+)/([^/\s#?]+)")
MD_LINK_RE = re.compile(r"\[\[?([^\]]+?)\]?\]\((?:[^)\s]+)\)")
TAG_RE = re.compile(r"<[^>]+>")
VERIFIED_RE = re.compile(r"Star counts last verified:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")


# ---------------------------------------------------------------- parsing

def clean(text: str) -> str:
    """Strip HTML tags/badges, markdown links and bold markers; collapse whitespace."""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = TAG_RE.sub("", text)
    text = MD_LINK_RE.sub(r"\1", text)
    text = text.replace("**", "").replace("__", "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def section_title(heading: str) -> str:
    """'## 🧪 Autonomous Research Systems' -> 'Autonomous Research Systems'."""
    text = heading.lstrip("#").strip()
    m = re.search(r"[A-Za-z0-9]", text)
    return text[m.start():].strip() if m else text


def split_row(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def parse_framework(cell: str) -> tuple[str, str]:
    """'<b>Tools:</b> X<br><b>LLM APIs:</b> Y' -> ('X', 'Y')."""
    tools, apis = "", ""
    for part in re.split(r"<br\s*/?>", cell, flags=re.I):
        m = re.match(r"\s*<b>\s*([^<:]+?)\s*:?\s*</b>\s*:?\s*(.*)$", part.strip(), flags=re.I | re.S)
        if not m:
            if part.strip() and not tools:
                tools = clean(part)
            continue
        label, value = m.group(1).lower(), clean(m.group(2))
        if label.startswith("tool") or label.startswith("framework"):
            tools = value
        elif "llm" in label or "api" in label:
            apis = value
    return tools, apis


def parse_readme(text: str) -> list[dict]:
    """Return one dict per table row, in README order."""
    entries: list[dict] = []
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = section_title(line)
            continue
        if not section or not ROW_RE.match(line):
            continue
        cells = split_row(line)
        m = LINK_CELL_RE.match(cells[0])
        if not m:
            continue
        name, url = m.group(1).strip(), m.group(2).strip()
        gm = GH_REPO_RE.match(url)
        repo = "%s/%s" % (gm.group(1), gm.group(2).removesuffix(".git")) if gm else ""
        desc = clean(cells[1]) if len(cells) > 1 else ""
        tools, apis = parse_framework(cells[2]) if len(cells) > 2 else ("", "")
        entries.append({
            "section": section,
            "name": clean(name),
            "url": url,
            "repo": repo,
            "description": desc,
            "tools": tools,
            "apis": apis,
            "claude_code": bool(CLAUDE_RE.search(tools + " " + apis)),
        })
    return entries


def verified_date(text: str) -> str:
    m = VERIFIED_RE.search(text)
    return m.group(1) if m else "?"


# ---------------------------------------------------------------- fetching

def _gh(*args: str) -> str | None:
    if not shutil.which("gh"):
        return None
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8",
                             timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _http(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "auto-research-tools-refresh",
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https hosts)
            return r.read().decode("utf-8")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def fetch_readme() -> str:
    b64 = _gh("api", "repos/%s/readme" % UPSTREAM_REPO, "--jq", ".content")
    if b64:
        return base64.b64decode(b64).decode("utf-8")
    text = _http(RAW_URL)
    if text:
        return text
    raise SystemExit("could not fetch README (gh and raw.githubusercontent.com both failed)")


def fetch_sha() -> str:
    sha = _gh("api", "repos/%s/commits/HEAD" % UPSTREAM_REPO, "--jq", ".sha")
    if not sha:
        raw = _http("https://api.github.com/repos/%s/commits/HEAD" % UPSTREAM_REPO)
        try:
            sha = json.loads(raw)["sha"] if raw else None
        except (ValueError, KeyError, TypeError):
            sha = None
    return sha or "?"


def fetch_stars(repo: str) -> str:
    if not repo:
        return "?"
    val = _gh("api", "repos/%s" % repo, "--jq", ".stargazers_count")
    if val is None:
        raw = _http("https://api.github.com/repos/%s" % repo)
        try:
            val = str(json.loads(raw)["stargazers_count"]) if raw else None
        except (ValueError, KeyError, TypeError):
            val = None
    return val if val and val.isdigit() else "?"


def fetch_marketplace(repo: str) -> dict | None:
    """Return {'name': ..., 'plugins': [...]} if the repo ships .claude-plugin/marketplace.json."""
    if not repo:
        return None
    b64 = _gh("api", "repos/%s/contents/.claude-plugin/marketplace.json" % repo, "--jq", ".content")
    if b64 is None:
        raw = _http("https://api.github.com/repos/%s/contents/.claude-plugin/marketplace.json" % repo)
        try:
            b64 = json.loads(raw)["content"] if raw else None
        except (ValueError, KeyError, TypeError):
            b64 = None
    if not b64:
        return None
    try:
        data = json.loads(base64.b64decode(b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    plugins = sorted({str(p.get("name")) for p in data.get("plugins", []) if isinstance(p, dict) and p.get("name")})
    return {"name": str(data.get("name", "?")), "plugins": plugins}


# ---------------------------------------------------------------- rendering

def _cell(text: str) -> str:
    return (text or "-").replace("|", "\\|")


def _fmt_stars(stars: str) -> str:
    return "{:,}".format(int(stars)) if stars.isdigit() else "?"


def render_catalog(entries: list[dict], *, sha: str, generated: str, verified: str,
                   stars: dict[str, str], markets: dict[str, dict]) -> str:
    out = [
        "---",
        "type: reference",
        "source: %s" % UPSTREAM_URL,
        "license: CC0-1.0",
        "upstream_commit: %s" % sha,
        "generated: %s" % generated,
        "upstream_stars_verified: %s" % verified,
        "entries: %d" % len(entries),
        "---",
        "",
        "# Auto-research tools catalog",
        "",
        "> Generated by `scripts/refresh_catalog.py` from [%s](%s) (CC0-1.0, commit `%s`). "
        "Do not edit by hand; re-run the script." % (UPSTREAM_REPO, UPSTREAM_URL, sha[:12]),
        "> Stars = live `stargazers_count` fetched on %s (`?` = lookup failed). "
        "Upstream verified its own counts on %s." % (generated, verified),
        "> CC = `yes` when Tools/LLM APIs mention Claude Code, Claude Skill, Agent Skills or MCP. "
        "Marketplace = repo ships `.claude-plugin/marketplace.json` (checked for CC rows only).",
        "",
    ]
    sections: list[str] = []
    for e in entries:
        if e["section"] not in sections:
            sections.append(e["section"])
    out.append("| Section | Stage | Tools |")
    out.append("|---|---|---|")
    for s in sections:
        out.append("| %s | %s | %d |" % (_cell(s), _cell(SECTION_STAGES.get(s, "")),
                                         sum(1 for e in entries if e["section"] == s)))
    out.append("")
    for s in sections:
        out.append("## %s" % s)
        out.append("")
        if s in SECTION_STAGES:
            out.append("Stage: %s" % SECTION_STAGES[s])
            out.append("")
        out.append("| Tool | Stars | CC | Description | Tools / LLM APIs |")
        out.append("|---|---:|:-:|---|---|")
        for e in (x for x in entries if x["section"] == s):
            fw = e["tools"] or "-"
            if e["apis"]:
                fw += " · APIs: " + e["apis"]
            out.append("| [%s](%s) | %s | %s | %s | %s |" % (
                _cell(e["name"]), e["url"], _fmt_stars(stars.get(e["repo"], "?")),
                "yes" if e["claude_code"] else "no", _cell(e["description"]), _cell(fw)))
        out.append("")
    out.append("## Claude Code install paths")
    out.append("")
    cc = [e for e in entries if e["claude_code"]]
    if not cc:
        out.append("None of the entries mention Claude Code.")
    else:
        out.append("| Tool | Repo | Marketplace | Plugins |")
        out.append("|---|---|---|---|")
        for e in cc:
            mk = markets.get(e["repo"])
            if mk:
                out.append("| %s | `%s` | `%s` | %s |" % (
                    _cell(e["name"]), e["repo"], _cell(mk["name"]),
                    _cell(", ".join("`%s`" % p for p in mk["plugins"]) or "-")))
            else:
                out.append("| %s | `%s` | none found | - |" % (_cell(e["name"]), e["repo"] or "-"))
        out.append("")
        out.append("Marketplace rows: `claude plugin marketplace add <repo>` then "
                   "`claude plugin install <plugin>@<marketplace>`. Re-verify before installing.")
    out.append("")
    return "\n".join(out)


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--readme", type=Path, help="parse this local README instead of fetching")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-stars", action="store_true", help="skip star and marketplace lookups")
    ap.add_argument("--sha", help="override upstream commit sha")
    ap.add_argument("--date", help="override generated date (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    text = args.readme.read_text(encoding="utf-8") if args.readme else fetch_readme()
    entries = parse_readme(text)
    if not entries:
        print("ERROR: no table rows parsed", file=sys.stderr)
        return 1
    sha = args.sha or ("?" if args.no_stars and args.readme else fetch_sha())
    stars: dict[str, str] = {}
    markets: dict[str, dict] = {}
    if not args.no_stars:
        for e in entries:
            if e["repo"] and e["repo"] not in stars:
                stars[e["repo"]] = fetch_stars(e["repo"])
            if e["claude_code"] and e["repo"] and e["repo"] not in markets:
                mk = fetch_marketplace(e["repo"])
                if mk:
                    markets[e["repo"]] = mk
    generated = args.date or _dt.date.today().isoformat()
    content = render_catalog(entries, sha=sha, generated=generated, verified=verified_date(text),
                             stars=stars, markets=markets)
    changed = write_if_changed(args.out, content)
    missing = sum(1 for e in entries if stars.get(e["repo"], "?") == "?")
    print("entries=%d sections=%d claude_code=%d stars_missing=%d marketplaces=%d %s %s" % (
        len(entries), len({e["section"] for e in entries}), sum(e["claude_code"] for e in entries),
        missing, len(markets), "wrote" if changed else "unchanged", args.out.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
