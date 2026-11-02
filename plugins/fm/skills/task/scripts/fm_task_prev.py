"""«## Өмнөх» — шинэ task-ийг тухайн төслийн өмнөх task-уудтай холбоно (itge.e 2026-11-02).

Хэмжилт (2026-11-02): 562 task-ийн 89% нь төсөлтэй ч зөвхөн 20% нь нэг төслийн өмнөх task руу холбоостой байв —
task «харьяалагддаг» ч урсгалын нэг хэсэг болдоггүй. fm_task.py new ба relay.py task хоёулаа үүнийг дуудна.
"""
import re
from pathlib import Path

_FM = re.compile(r"^---\n(.*?)\n---", re.S)


def _stem(link: str) -> str:
    v = (link or "").strip().strip("'\"")
    m = re.search(r"\[\[([^\]|#]+)", v)
    v = m.group(1) if m else v
    return v.replace("\\", "/").split("/")[-1].removesuffix(".md").strip()


def _field(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.M)
    return m.group(1).strip() if m else ""


def previous_tasks(tasks_dir: Path, project: str, exclude: str = "", n: int = 3):
    """→ [(stem, status, date)] — same-project tasks, newest first (completed/started/date)."""
    want = _stem(project)
    if not want: return []
    rows = []
    for p in tasks_dir.glob("*.md"):
        if p.stem == exclude: continue
        try: head = p.read_text(encoding="utf-8", errors="ignore")[:3000]
        except OSError: continue
        m = _FM.match(head)
        if not m or not re.search(r"^type:\s*task\b", m.group(1), re.M): continue
        fm = m.group(1)
        if _stem(_field(fm, "project")) != want: continue
        when = max(_field(fm, k)[:16] for k in ("completed", "started", "date"))
        rows.append((p.stem, _field(fm, "status") or "?", when))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:n]


def section(tasks_dir: Path, project: str, exclude: str = "", rel_dir: str = "01-GTD/Tasks") -> str:
    """Markdown «## Өмнөх» block, or "" when the project has no earlier tasks."""
    rows = previous_tasks(tasks_dir, project, exclude)
    if not rows: return ""
    lines = ["## Өмнөх", "", "Энэ task юуны үргэлжлэл вэ (автоматаар санал болгов: хамаарахгүйг хас, дутууг нэм):"]
    lines += [f"- [[{rel_dir}/{s}]] · {st} · {d[:10]}" for s, st, d in rows]
    return "\n".join(lines) + "\n"
