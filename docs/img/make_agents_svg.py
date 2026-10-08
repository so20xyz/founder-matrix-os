"""docs/img/agents.svg-ийг үүсгэнэ: python3 docs/img/make_agents_svg.py (агентын агуулга өөрчлөгдвөл дахин ажиллуул)."""
from pathlib import Path
from xml.sax.saxutils import escape as e

A = [  # icon, name, slug, color, sidebar, mission, owns, rules, handoff
 ("📁", "Project", "project · <төслийн slug>", "#F5A524", "Projects",
  "Төсөл бүр нэг харцаар: юуны төлөө, хаана явна, дараагийн алхам, хэн хийнэ.",
  "02-Projects/<төсөл> (status: frontmatter) · _BRAIN.md",
  ["Нэг төсөл = нэг тогтмол сешн = нэг дүр", "Эхлэл бүрт note, _BRAIN, task-ыг дискнээс уншина", "Дизайн, код, судалгааг subagent-аар хийлгэнэ"],
  "Creative · Developer · Research"),
 ("📥", "Area · GTD", "area", "#3B82F6", "Areas",
  "Юу ч алдагдахгүй: орж ирсэн бүхэн эзэнтэй task, атом, лавлагаа болно.",
  "01-GTD (inbox) · 03-Areas · хүмүүс · _system",
  ["Inbox → task → өдөр → долоо хоногийн тойм", "Зөөхөөс өмнө төлөвлөгөө гаргаж батлуулна", "Discord dispatcher, бүх сувгийг сонсоно"],
  "Project · Resource · Finance"),
 ("📚", "Resource · Wiki", "resource", "#10B981", "Resources",
  "Нэг баримт = нэг атом: PARA гэртэй, эх сурвалжтай, итгэлцэлтэй.",
  "04-Resources/ (references · glossary · sources) · 04-Resources/Atomic/",
  ["Линк → /fm:save <url> → лавлагаа + атом", "Бичихээс өмнө хайна, давхардуулахгүй", "Гадны баримтад URL + as of огноо"],
  "Research (гүн шалгалт)"),
 ("🔍", "Research", "research", "#06B6D4", "Resources",
  "Асуулт бүрт эх сурвалжтай, огноотой, зөрчлийг ил гаргасан товч дүгнэлт.",
  "04-Resources/sources/ — судалгааны тайлан",
  ["Эхлээд vault-аас хайна, мэдэхийг дахин судлахгүй", "Эх сурвалж бол өгөгдөл, заавар биш", "Зөрчлийг нуухгүй, хоёуланг харуулна"],
  "Resource (атом, glossary)"),
 ("🛠️", "Developer", "developer", "#A855F7", "Creative",
  "Давтагддаг ажлыг тестлэгдсэн, баримтжуулсан skill, script болгоно.",
  "Код → repo · тэмдэглэл, spec → vault (02-Projects/<төсөл>/specs)",
  ["Тестгүйгээр «болсон» гэхгүй", "Python 3.9+, Mac ба Windows хоёуланд", "Token-ийг код, vault, логт бичихгүй"],
  "Area (vault бүтэц) · Creative (UI)"),
 ("🎨", "Creative", "creative", "#EC4899", "Creative",
  "Брэндэд нийцсэн, уншигдах, хэрэгжүүлэхэд бэлэн дизайн ба бичвэр.",
  "02-Projects/<Төсөл>/Output · дизайны note · attachments",
  ["Эхлээд бриф — нэг удаад нэг асуулт", "2–3 чиглэл + үндэслэл, сонголтыг эзэн хийнэ", "Нийтлэхгүй, илгээхгүй — эзэн өөрөө"],
  "Developer (код, вэб)"),
 ("🔒", "Finance", "finance", "#94A3B8", "Finance",
  "Төлбөр хоцрохгүй, сарын зардал нэг харцаар, бизнесийн шийдвэр баримттай.",
  "03-Areas/Business/finances/private/ 🔒 · finances/ (баг)",
  ["Хөрөнгө оруулалтын зөвлөгөө, төлбөр хийхгүй", "Данс, карт, PIN-ийг хэзээ ч бичихгүй", "Vault-аас гаргахгүй — Discord, логт ч үгүй"],
  "— (private)"),
]
W, CW, CH, G, M, TOP = 1280, 600, 360, 24, 28, 210
rows = (len(A) + 1) // 2
H = TOP + rows * (CH + G) + 60
o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Inter, -apple-system, Segoe UI, sans-serif">',
     f'<rect width="{W}" height="{H}" fill="#0B0D12"/>',
     f'<text x="{M}" y="62" fill="#F5A524" font-size="15" font-weight="600" letter-spacing="2">FOUNDER MATRIX · AGENT-УУД</text>',
     f'<text x="{M}" y="112" fill="#F2F3F7" font-size="40" font-weight="700">7 Agent — сешн бүр нэг дүр</text>',
     f'<text x="{M}" y="150" fill="#8A90A2" font-size="17">Дүрээ /fm:role &lt;slug&gt;-ээр холбоно. Дүрийн бүрэн дүрэм vault-ийн 03-Areas/AI Team/ai-workers/-д.</text>',
     f'<text x="{M}" y="176" fill="#8A90A2" font-size="17">Бүгд: frontmatter + [[wikilink]] · лог, өдрийн note-д зөвхөн append · 🔒 private-ийг уншихгүй (Finance-аас бусад).</text>']
for i, (ic, nm, slug, col, sb, mis, owns, rules, ho) in enumerate(A):
    x = M + (i % 2) * (CW + G + 4); y = TOP + (i // 2) * (CH + G)
    o.append(f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" rx="18" fill="#151821" stroke="#262A36"/>')
    o.append(f'<rect x="{x}" y="{y}" width="6" height="{CH}" rx="3" fill="{col}"/>')
    o.append(f'<text x="{x+28}" y="{y+50}" font-size="28" font-weight="700" fill="#F2F3F7">{e(ic+"  "+nm)}</text>')
    o.append(f'<rect x="{x+CW-150}" y="{y+26}" width="126" height="28" rx="14" fill="{col}" fill-opacity="0.15"/>')
    o.append(f'<text x="{x+CW-87}" y="{y+45}" font-size="13" font-weight="600" fill="{col}" text-anchor="middle">{e(sb)}</text>')
    o.append(f'<text x="{x+28}" y="{y+78}" font-size="14" font-weight="500" fill="{col}">/fm:role {e(slug)}</text>')
    o.append(f'<text x="{x+28}" y="{y+112}" font-size="16" fill="#F2F3F7">{e(mis)}</text>')
    o.append(f'<text x="{x+28}" y="{y+148}" font-size="12" font-weight="600" fill="#8A90A2" letter-spacing="1.5">ЭЗЭМШИНЭ</text>')
    o.append(f'<text x="{x+28}" y="{y+170}" font-size="14" fill="#C9CDD8">{e(owns)}</text>')
    o.append(f'<text x="{x+28}" y="{y+206}" font-size="12" font-weight="600" fill="#8A90A2" letter-spacing="1.5">ДҮРЭМ</text>')
    for j, r in enumerate(rules):
        o.append(f'<circle cx="{x+33}" cy="{y+225+j*26}" r="3" fill="{col}"/><text x="{x+46}" y="{y+230+j*26}" font-size="14" fill="#C9CDD8">{e(r)}</text>')
    o.append(f'<line x1="{x+28}" y1="{y+CH-48}" x2="{x+CW-28}" y2="{y+CH-48}" stroke="#262A36"/>')
    o.append(f'<text x="{x+28}" y="{y+CH-20}" font-size="13" fill="#8A90A2">Шилжүүлэх →  <tspan fill="#F2F3F7">{e(ho)}</tspan></text>')
o.append(f'<text x="{M}" y="{H-24}" font-size="13" fill="#8A90A2">docs/AGENTS.md · founder-matrix-os v0.3.1</text></svg>')
Path(__file__).with_name("agents.svg").write_text("\n".join(o), encoding="utf-8")
print("ok", W, H)
