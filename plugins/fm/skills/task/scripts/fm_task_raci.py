"""Task-ийн RACI анхдагч утга (itge.e 2026-11-03: «дүрэм мөн шүүдээ»).

Шийдвэрүүд: 2026-10-14 «Task бүр RACI-тай байна» (хавтгай талбар responsible, accountable ганц, consulted, informed),
2026-10-25 «itge.e-ийн RACI үүрэг төслийн төрлөөр» (клиентийн төсөлд itge.e = A; дотоод төсөлд A = төслийн сешн),
2026-10-26 «хүн ба agent ижил RACI дүр авна». fm_task.py new ба relay.py task хоёулаа дуудна.
R = owner · A = клиент/төсөлгүй → me, дотоод төсөл → project · C = гараар · I = me.
"""
import re
from pathlib import Path


def _project_business(vault: Path, project: str) -> str:
    rel = re.sub(r"^\[\[|\]\]$", "", (project or "").strip().strip('"')).split("|")[0].removesuffix(".md")
    if not rel: return ""
    p = vault / (rel + ".md")
    try: head = p.read_text(encoding="utf-8", errors="ignore")[:3000]
    except OSError: return ""
    m = re.search(r"^business:\s*\"?([\w-]+)", head, re.M)
    return m.group(1).lower() if m else ""


def defaults(vault: Path, owner: str, project: str = "") -> dict:
    """→ {responsible, accountable, informed} — consulted гараар (заавал биш)."""
    r = (owner or "me").strip().strip('"')
    biz = _project_business(Path(vault), project) if project else ""
    a = "project" if (project and biz != "client") else "me"
    return {"responsible": r, "accountable": a, "informed": '["me"]'}
