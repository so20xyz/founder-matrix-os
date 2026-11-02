"""«## Өмнөх» — шинэ task-ийг эзний (төсөл эсвэл area) өмнөх task-уудтай холбоно (itge.e 2026-11-02).

Хэмжилт (2026-11-02): 562 task-ийн 89% нь төсөлтэй ч зөвхөн 20% нь нэг төслийн өмнөх task руу холбоостой байв —
task «харьяалагддаг» ч урсгалын нэг хэсэг болдоггүй. Task зөвхөн төслийнх биш: area-гийн байнгын task ч
өмнөхтэйгээ уялдана. fm_task.py new ба relay.py task хоёулаа үүнийг дуудна.
"""
import re
from pathlib import Path

_FM = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)


def _stem(link: str) -> str:
    v = (link or "").strip().strip("'\"")
    m = re.search(r"\[\[([^\]|#]+)", v)
    v = m.group(1) if m else v
    return v.replace("\\", "/").split("/")[-1].removesuffix(".md").strip()


def _field(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    return m.group(1).strip() if m else ""


def _links(fm: str, key: str):
    """Stems of `key:` — scalar, inline list or block list («  - "[[x]]"»)."""
    m = re.search(rf"^{key}:[ \t]*(.*)$((?:\r?\n[ \t]+-[^\n]*)*)", fm, re.M)
    if not m: return set()
    raw = m.group(1) + "\n" + m.group(2)
    found = re.findall(r"\[\[([^\]|#]+)", raw)
    if not found and m.group(1).strip(): found = [m.group(1)]
    return {_stem(x) for x in found if _stem(x)}


def previous_tasks(tasks_dir: Path, link: str, exclude: str = "", n: int = 3, fields=("project",)):
    """→ [(stem, status, date)] — tasks whose `fields` link to `link`, newest first (completed/started/date)."""
    want = _stem(link)
    if not want: return []
    rows = []
    for p in tasks_dir.glob("*.md"):
        if p.stem == exclude: continue
        try: head = p.read_text(encoding="utf-8", errors="ignore")[:3000]
        except OSError: continue
        m = _FM.match(head)
        if not m or not re.search(r"^type:\s*task\b", m.group(1), re.M): continue
        fm = m.group(1)
        if not any(want in _links(fm, f) for f in fields): continue
        when = max(_field(fm, k)[:16] for k in ("completed", "started", "date"))
        rows.append((p.stem, _field(fm, "status") or "?", when))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:n]


def section(tasks_dir: Path, project: str = "", exclude: str = "", rel_dir: str = "01-GTD/Tasks", area: str = "") -> str:
    """Markdown «## Өмнөх» block (project tasks first, else the area's), or "" when there are none."""
    rows = previous_tasks(tasks_dir, project, exclude) if project else []
    if not rows and area:
        rows = previous_tasks(tasks_dir, area, exclude, fields=("areas", "area"))
    if not rows: return ""
    lines = ["## Өмнөх", "", "Энэ task юуны үргэлжлэл вэ (автоматаар санал болгов: хамаарахгүйг хас, дутууг нэм):"]
    lines += [f"- [[{rel_dir}/{s}]] · {st} · {d[:10]}" for s, st, d in rows]
    return "\n".join(lines) + "\n"
