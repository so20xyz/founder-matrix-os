"""Task-ийн RACI анхдагч утга (itge.e 2026-11-03: «дүрэм мөн шүүдээ»).

Шийдвэрүүд: 2026-10-14 «Task бүр RACI-тай байна» (хавтгай талбар responsible, accountable ганц, consulted, informed),
2026-10-25 «itge.e-ийн RACI үүрэг төслийн төрлөөр» (клиентийн төсөлд itge.e = A; дотоод төсөлд A = төслийн сешн),
2026-10-26 «хүн ба agent ижил RACI дүр авна». fm_task.py new ба relay.py task хоёулаа дуудна.
R = owner · A = клиент/төсөлгүй → me, дотоод төсөл → project · C = гараар · I = me.
"""
import re
from pathlib import Path


CREATIVE_PROJECT_TYPES = {"website", "content", "course"}   # Creative Director шаардлагатай төслийн төрөл
CREATIVE_TASK_TYPES = {"design", "content"}


def _project_field(vault: Path, project: str, key: str) -> str:
    rel = re.sub(r"^\[\[|\]\]$", "", (project or "").strip().strip('"')).split("|")[0].removesuffix(".md")
    if not rel: return ""
    p = vault / (rel + ".md")
    try: head = p.read_text(encoding="utf-8", errors="ignore")[:3000]
    except OSError: return ""
    m = re.search(rf"^{key}:\s*\"?(?:\[\[)?([^\]\"\n]+)", head, re.M)
    return m.group(1).split("/")[-1].strip().lower() if m else ""


def defaults(vault: Path, owner: str, project: str = "", task_type: str = "") -> dict:
    """→ {responsible, accountable, informed[, consulted]}.
    C (itge.e 2026-11-03): Creative Director шаардлагатай ажилд itge.e = consulted — owner creative, task-type design/content,
    эсвэл төслийн project-type website/content/course."""
    r = (owner or "me").strip().strip('"')
    vault = Path(vault)
    biz = _project_field(vault, project, "business") if project else ""
    a = "project" if (project and biz != "client") else "me"
    out = {"responsible": r, "accountable": a, "informed": '["me"]'}
    tt = re.sub(r"^\[\[|\]\]$", "", (task_type or "").strip().strip('"')).split("/")[-1].lower()
    ptype = _project_field(vault, project, "project-type") if project else ""
    if r.lower().startswith("creative") or tt in CREATIVE_TASK_TYPES or ptype in CREATIVE_PROJECT_TYPES:
        out["consulted"] = '["me"]'
    return out
