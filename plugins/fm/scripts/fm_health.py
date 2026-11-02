#!/usr/bin/env python3
"""fm_health — системийн давхаргуудын зөрүүг шалгана (itge.e 2026-11-02: «хаана алдаад байгааг мэдэхгүй байна»).
Vault-ын агуулгыг fm_vault_check/fm_lint шалгадаг; энэ нь тохиргоо ↔ BOOT ↔ hook ↔ plugin ↔ санах ойн зөрүүг.
   python fm_health.py [--vault PATH] [--json]
Гаралт: мөр бүр «✅|⚠|❌ шалгалт — тайлбар»; exit 1 = ❌ байвал."""
import json, os, re, sys
from pathlib import Path

HOME = Path.home()
VAULT = Path(sys.argv[sys.argv.index("--vault") + 1]) if "--vault" in sys.argv else (
    Path("D:/My Drive/Second Brain 2.0") if os.name == "nt" else HOME / "My Drive/Second Brain 2.0")
RES = []


def add(level, name, msg): RES.append((level, name, msg))


def rj(p, d=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return d


def check_broadcast():
    d = rj(VAULT / "_system/fm/discord.json", {}) or {}
    bc, disp = d.get("broadcast", "03-sys-admin"), d.get("dispatcher_role", "gtd")
    if bc == disp: add("⚠", "broadcast", f"broadcast = #{bc} (itge.e-ийн суваг); relay зөвхөн GTD-д сонсгодог (2f35a4b) — тусдаа sys суваг хийх нь цэвэр")
    else: add("✅", "broadcast", f"#{bc}")


def check_boot_size():
    # _CLAUDE.md inject хийгддэггүй (лавлах) — сешн бүрийн ачаалал = BOOT.md + hook-ийн контекст л
    for rel, lim in (("_system/BOOT.md", 12_000),):
        p = VAULT / rel
        if not p.exists(): continue
        n = p.stat().st_size
        add("⚠" if n > lim else "✅", f"size {rel}", f"{n // 1024} KB (зорилт ≤{lim // 1024} KB)")


def _cmd_paths(cmd):
    return [Path(m) for m in re.findall(r'"([^"]+\.(?:py|mjs|js|sh|ps1))"', cmd)]


def check_hooks():
    s = rj(HOME / ".claude/settings.json", {}) or {}
    bad, n = [], 0
    for ev, groups in (s.get("hooks") or {}).items():
        for g in groups:
            for h in g.get("hooks", []):
                for p in _cmd_paths(h.get("command", "")):
                    n += 1
                    if "${" not in str(p) and not p.exists(): bad.append(f"{ev}: {p}")
    add("❌" if bad else "✅", "hook paths", f"{len(bad)}/{n} алга: " + "; ".join(bad[:5]) if bad else f"{n} зам бүгд бий")


def check_plugin_cache():
    base = HOME / ".claude/plugins/cache/founder-matrix/fm"
    if not base.exists(): return
    vs = sorted((p.name for p in base.iterdir() if p.is_dir()), key=lambda v: [int(x) for x in re.findall(r"\d+", v)])
    inst = rj(HOME / ".claude/plugins/installed_plugins.json", {}) or {}
    active = [e.get("version") for k, arr in (inst.get("plugins") or {}).items() if k.startswith("fm@") for e in arr]
    add("⚠" if len(vs) > 3 else "✅", "plugin cache", f"fm-ийн {len(vs)} хувилбар кэшд (сүүлийн {vs[-1]}), идэвхтэй: {', '.join(map(str, active)) or '?'}")
    repo = Path("D:/CodeBase/founder-matrix-os/plugins/fm/.claude-plugin/plugin.json")
    rv = (rj(repo, {}) or {}).get("version")
    if rv and active and rv not in active: add("⚠", "plugin version", f"repo {rv} ≠ суусан {', '.join(map(str, active))} — `/plugin update`")


def check_memory():
    mem = VAULT / "_system/fm/claude/memory"
    if not mem.exists(): mem = next((HOME / ".claude/projects").glob("*Second-Brain*/memory"), None)
    if not mem or not mem.exists(): add("⚠", "memory", "хавтас олдсонгүй"); return
    files = [p for p in mem.glob("*.md") if p.name != "MEMORY.md"]
    idx = (mem / "MEMORY.md").read_text(encoding="utf-8") if (mem / "MEMORY.md").exists() else ""
    linked = set(re.findall(r"\]\(([^)]+\.md)\)", idx))
    missing = [l for l in linked if not (mem / l).exists()]
    orphan = [p.name for p in files if p.name not in linked]
    add("⚠" if len(files) > 40 else "✅", "memory count", f"{len(files)} бичлэг (зорилт ≤40)")
    if missing: add("❌", "memory index", f"индексэд байгаа ч файлгүй: {', '.join(missing[:5])}")
    if orphan: add("⚠", "memory orphan", f"индексгүй файл {len(orphan)}: {', '.join(orphan[:5])}")
    # давхардал: тайлбарын үгийн давхцал ≥ 60%
    desc = {}
    for p in files:
        m = re.search(r"^description:\s*(.+)$", p.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m: desc[p.name] = set(re.findall(r"[\wА-Яа-яӨөҮүЁё#]{3,}", m.group(1).lower()))
    names, dup = list(desc), []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            u = desc[a] | desc[b]
            if u and len(desc[a] & desc[b]) / len(u) >= 0.5: dup.append(f"{a} ~ {b}")
    if dup: add("⚠", "memory dup", f"{len(dup)} хос төстэй: " + "; ".join(dup[:4]))


def check_drive_dupes():
    hits = [str(p.relative_to(VAULT)) for p in VAULT.rglob("* (1).*") if not {".obsidian", "_trash", ".backups"} & set(p.parts)]
    add("⚠" if hits else "✅", "drive (1) files", f"{len(hits)}: " + "; ".join(hits[:5]) if hits else "алга")


def check_registry():
    reg = rj(VAULT / "_system/fm/registry.json", {}) or {}
    ch = rj(VAULT / "_system/fm/channels.json", {}) or {}
    ss = reg.get("sessions", {})
    norole = [s.get("name") for s in ss.values() if not s.get("role")]
    add("⚠" if norole else "✅", "registry", f"{len(ss)} сешн, дүргүй {len(norole)}" + (f": {', '.join(map(str, norole[:5]))}" if norole else ""))


def check_hook_text():
    """SessionStart-ийн заавар дахь скриптийн зам бодит эсэх (10-р сард scripts/ → plugins/fm/scripts/ шилжсэн)."""
    repo = Path("D:/CodeBase/founder-matrix-os")
    stale = []
    for src in (repo / "plugins/fm/tools/relay").glob("*.py"):
        for m in re.findall(r"founder-matrix-os[\\/]+((?:scripts|tools)[\\/][\w/\\.-]+\.py)", src.read_text(encoding="utf-8", errors="ignore")):
            if not (repo / m.replace("\\", "/")).exists(): stale.append(f"{src.name}: {m}")
    add("⚠" if stale else "✅", "hook text paths", "; ".join(sorted(set(stale))[:4]) if stale else "бүгд бий")


def check_goom_sync():
    """Vault -> Second Brain sync (itge.e 2026-11-02: goom-tick 7 цаг гацаж, токен дуусан ч хэн ч мэдээгүй)."""
    import base64, time
    cfg = rj(HOME / ".fmos/goom.json")
    if not cfg: return
    try:
        p = cfg["token"].split(".")[1]; exp = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))["exp"]
        left = int(exp - time.time())
        add("❌" if left < 0 else "✅", "goom token", f"хугацаа дууссан {-left // 60} мин өмнө (goom-tick гацсан?)" if left < 0 else f"{left // 3600} цаг үлдсэн")
    except Exception as e: add("⚠", "goom token", f"уншиж чадсангүй: {e}")
    log = HOME / ".fmos/goom-pull.log"
    if log.exists():
        age = int((time.time() - log.stat().st_mtime) // 60)
        add("❌" if age > 10 else "✅", "goom-tick", f"сүүлд {age} мин өмнө ажилласан" + (" — гацсан байж магадгүй (Task Scheduler goom-tick)" if age > 10 else ""))


def check_task_flow():
    """Төсөлтэй task-ийн хэд нь өмнөх task руугаа холбоостой вэ (itge.e 2026-11-02: 20% байв, «## Өмнөх» нэмэв)."""
    tdir = VAULT / "01-GTD/Tasks"
    if not tdir.exists(): return
    names, rows = set(), []
    for p in tdir.glob("*.md"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        m = re.match(r"---\n(.*?)\n---", t, re.S)
        if not m or not re.search(r"^type:\s*task", m.group(1), re.M): continue
        pr = re.search(r"^project:[ \t]*(\S.*)$", m.group(1), re.M)
        names.add(p.stem)
        if pr and "[[" in pr.group(1): rows.append((p.stem, re.findall(r"\[\[([^\]|#]+)", t[m.end():])))
    linked = sum(1 for s, ls in rows if any(l.split("/")[-1] in names and l.split("/")[-1] != s for l in ls))
    pct = round(100 * linked / len(rows)) if rows else 0
    add("⚠" if pct < 50 else "✅", "task flow", f"төсөлтэй {len(rows)} task-ийн {pct}% нь өмнөх task руугаа холбоостой (зорилт ≥50%)")


for f in (check_broadcast, check_boot_size, check_hooks, check_plugin_cache, check_memory, check_drive_dupes, check_registry, check_hook_text, check_goom_sync, check_task_flow):
    try: f()
    except Exception as e: add("❌", f.__name__, f"шалгалт унав: {e}")

if "--json" in sys.argv: print(json.dumps(RES, ensure_ascii=False, indent=1))
else:
    for lv, n, m in RES: print(f"{lv} {n} — {m}")
    print(f"\n❌ {sum(r[0] == '❌' for r in RES)} · ⚠ {sum(r[0] == '⚠' for r in RES)} · ✅ {sum(r[0] == '✅' for r in RES)}")
sys.exit(1 if any(r[0] == "❌" for r in RES) else 0)
