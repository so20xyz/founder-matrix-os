# -*- coding: utf-8 -*-
"""Skills уншварыг үүсгэнэ: articles/skills/index.html (суу-билиг уншварын бүрхүүл дээр).
Бичвэрийн эх сурвалж энэ файл. Дараа нь `python build.py` стандарт хэсгүүдийг (toc, rv, anav) нэмнэ."""
import pathlib, re

SITE = pathlib.Path(r"D:/My Drive/Second Brain 2.0/02-Projects/itge.online/Output/site")
s = (SITE / "articles/suu-bilig/index.html").read_text(encoding="utf-8")

TITLE = "Skills: agent ажлаа яаж зөв дарааллаар хийдэг вэ"
DEK = "Superpowers гэсэн нэг багц skill agent-ийг «шууд код бичих»-ээс өмнө асуулга, дизайн, төлөвлөгөөгөөр дамжуулдаг. Өнөөдрийн GTD самбар нэг өдөрт гурван хувилбар болсон түүхээр харуулъя."
DESC = "Superpowers skill-ийн дараалал (brainstorming → дизайн → төлөвлөгөө → subagent → шалгалт) бодит жишээгээр: GTD самбар v1 → v3."

BODY = '''<div class="card goals"><small>ЭНЭ НИЙТЛЭЛЭЭР</small><p>→  Skill гэж юу, agent яагаад түүнийг заавал уншдаг вэ</p><p>→  Superpowers-ийн таван алхам, алхам бүрийн хориг</p><p>→  Өнөөдрийн GTD самбар v1 → v3 хэрхэн гарсан</p><p>→  Өөрийн ажилд өнөөдөр хэрэглэх нэг дүрэм</p></div>
<h2 id="s1">01. Нэг өдөрт гурван хувилбар</h2>
<p>Өнөө өглөө 10-р сарын 29-нд itge.e GTD самбарыг шинээр бодож эхэлсэн. Эхний хүсэлт энгийн байсан: «юу болж байна, дараа нь юу хийх вэ» гэсэн хоёр асуултад нэг харцаар хариулдаг самбар. Орой болтол нэг дэлгэц гурван удаа өөрчлөгдсөн: v1 цайвар, v2 хар, v3 тод өнгийн хатуу блоктой.</p>
<figure class="imgs"><div class="irow n2"><img src="../../assets/img/skills-v1.jpg" alt="GTD самбар v1: цайвар дэвсгэр, цагийн шугам, дараагийн алхам" loading="lazy" style="aspect-ratio:1100/1231"><img src="../../assets/img/skills-v3.jpg" alt="GTD самбар v3: хар дэвсгэр, тод өнгийн блок, хичээлийн embed" loading="lazy" style="aspect-ratio:1100/1219"></div><figcaption>Зүүн талд v1, баруун талд v3 · Figma «Second Brain», 2026-10-29</figcaption></figure>
<p>Гурван хувилбар гарсан нь алдаа биш. Хүн харсны дараа л мэддэг тул эхний зураг нь асуулт тавьдаг. Асуудал нь хувилбар бүр өмнөхөө орхиод, дараагийнхыг таамгаар зурвал өдөр дуустал тойрон эргэнэ. Skill яг энэ тойргийг богиносгоход зориулагдсан.</p>
<h2 id="s2">02. Skill гэж юу вэ</h2>
<p>Skill бол нэг хавтас доторх SKILL.md файл. Дээд талд нь «энэ skill хэзээ хэрэгтэй вэ» гэсэн нэг өгүүлбэр, доор нь «ингэж ажилла» гэсэн алхмууд бичигдсэн байна. Agent ажил авмагц тэр өгүүлбэрүүдийг уншиж, таарсан skill-ийг бүтнээр нь ачаалаад дагана. Өөрөө зохиох биш, бичигдсэн аргыг дагах нь гол санаа.</p>
<div class="card box"><small>НЭГ SKILL-ИЙН БҮТЭЦ</small><p>name · товч нэр (жишээ нь brainstorming)</p><p>description · «хэзээ ашиглах вэ» гэсэн нэг өгүүлбэр. Agent зөвхөн үүгээр шийддэг</p><p>бие · алхмууд, хориг, шалгах жагсаалт</p></div>
<p>Superpowers бол ийм skill-ийн нэг багц. Манай компьютер дээр 6.4.1 хувилбар суусан. Багцын хамгийн эхний skill нь «ямар ч хариу өгөхөөс өмнө тохирох skill байгаа эсэхийг шалга, 1 хувь ч тохирч магадгүй бол ачаал» гэж заадаг. Тиймээс agent «энэ жижиг юм» гэж алгасах эрхгүй.</p>
<h2 id="s3">03. Таван алхам</h2>
<ol class="steps"><li><b>1.</b><span><strong>Brainstorming.</strong> Юу хүсч байгааг ойлгох, ойлгосноо бичиж буцааж харуулах. Ажлыг гурван замын нэгээр ангилна: Spike (боломжтой эсэхийг шалгах), Bounded (байгаа зүйлд жижиг өөрчлөлт), Architectural (шинэ зүйл бүтээх).</span></li><li><b>2.</b><span><strong>Дизайн.</strong> Ойлголтыг дизайн болгож харуулна. Хүн «тийм» гэж хэлээгүй бол ямар ч бүтээгдэхүүний код бичихгүй. Энэ хоригийг skill өөрөө HARD-GATE гэж нэрлэдэг.</span></li><li><b>3.</b><span><strong>Төлөвлөгөө (writing-plans).</strong> Ажлыг жижиг даалгаваруудад хуваана: даалгавар бүрд аль файл, ямар код, хэрхэн шалгах вэ гэдгийг бичнэ. Төсөл дээр юу ч мэдэхгүй хүн ч гүйцэтгэж чадах түвшинд бичигдэнэ.</span></li><li><b>4.</b><span><strong>Subagent.</strong> Даалгавар бүрийг цэвэр толгойтой шинэ туслах agent гүйцэтгэнэ. Дараа нь тусдаа хянагч «заасан зүйлээ хийсэн үү, чанар хэр вэ» гэж шалгана. Нэг agent бүгдийг дангаараа хийхгүй.</span></li><li><b>5.</b><span><strong>Тест ба нотолгоо.</strong> Эхлээд тест бичиж, бүтэлгүйтэхийг нь харна. Дараа нь кодыг бичнэ. «Дууслаа» гэхээсээ өмнө шалгах командыг ажиллуулж, үр дүнг нь харуулна.</span></li></ol>
<div class="card box"><small>ХАМГИЙН ЧУХАЛ НЬ ХОРИГ</small><p>Дизайн батлагдаагүй бол код бичихгүй.</p><p>Тест бүтэлгүйтэхийг хараагүй бол тест зөв гэдгийг мэдэхгүй.</p><p>Шалгах командын үр дүнгүйгээр «болсон» гэж хэлэхгүй.</p></div>
<h2 id="s4">04. Самбарын түүхийг таван алхамаар харвал</h2>
<p>Өнөөдрийн ажилд бүх agent superpowers-ийн skill-ийг нэр заасаар дуудаагүй. Гэхдээ ажлын мөр яг тэр дарааллаар явсан нь task-ийн өөрчлөлтийн түүхэнд тод харагдаж байна. Тиймээс таван алхмыг самбарын бодит үйлдэлтэй зэрэгцүүлж харуулъя.</p>
<div class="tblw"><table><tr><th>Алхам</th><th>Самбар дээр юу болсон</th><th>Нотолгоо</th></tr>
<tr><td>Brainstorming</td><td>itge.e-ийн эх үг, 27 Pinterest pin, Stitch v2 дэлгэц, 10-26 прототип. Зургаан бүлэг: өнөөдөр, дараагийн алхам, хүлээгдэж буй, Inbox, өдрөө хаах, PARA цагийн шугам.</td><td>Figma «GTD самбар · moodboard»</td></tr>
<tr><td>Дизайн</td><td>v1: дөрвөн дэлгэц 1440 өргөнтэй, library-ийн бэлэн component-оор. itge.e коммент өгч, чиглэл өөрчилсөн.</td><td>section 812:3768</td></tr>
<tr><td>Төлөвлөгөө</td><td>v2: «Өглөө», Inbox, Өдрөө хаах, PARA тус бүр нэг дэлгэц. 8 component, дэлгэц бүр instance-аар.</td><td>section 812:4552, 812:4688</td></tr>
<tr><td>Subagent</td><td>Creative agent Figma-д v3-ыг зурна. Architect agent v3-ыг апп руу кодчилно. Хоёр тусдаа agent, нэг task.</td><td>section 814:5448 · goomnet c524276, 62d487b</td></tr>
<tr><td>Нотолгоо</td><td>Layout алдаа 0, contrast алдаа 0 гэж хэмжсэн. Апп-ын дэлгэцийг Figma-тай хос screenshot-оор тулгасан.</td><td>task-ийн өөрчлөлтийн түүх</td></tr></table></div>
<div class="compare"><div><small>Skill-гүй, шууд зурах</small><p>«Самбар хий» гэсэн нэг мөр хүсэлтээс шууд v1 гарна. Хүсэлтийн цаана нуугдсан «хичээл заах цагт самбар юу харуулах ёстой вэ» гэсэн шаардлага v1-д ороогүй үлддэг.</p></div><div><small>Skill-тэй</small><p>Эхлээд эх үгийг бүтнээр нь бичиж, харьцуулах pin-ээ цуглуулж, зургаан бүлэг гэж тохирсон. Тиймээс v3-д «Хичээл 03 19:00–22:00 ба материалын embed» нэг блок болж орсон.</p></div></div>
<h2 id="s5">05. Яагаад дараалал нь чухал вэ</h2>
<p>Agent бол хурдан бичдэг, гэхдээ «юу хүсч байна вэ» гэдгийг таамаглах хандлагатай. Таамаглал буруу бол хурдтай бичих нь буруу зүйлийг хурдан хийхтэй адил. Skill-ийн дараалал үүнийг хоёр газар зогсоодог: дизайныг батлуулахаас өмнө, дууссаныг мэдэгдэхээс өмнө.</p>
<p>Өнөөдрийн vault-д нэг ижил сургамж бичигдсэн: дутуу явцыг хувиар бүү зохио. Самбар дээрх «Season 2 · 57%» гэсэн тоо бодит task-ийн тооноос гарсан, зохиомол тоо биш. Энэ нь тавдугаар алхмын «нотолгоо» дүрмийн жижиг хувилбар.</p>
<h2 id="s6">06. Өөрөө туршиж үзэх нь</h2>
<ol class="steps"><li><b>1.</b><span>Claude Code-д ажлаа нэг өгүүлбэрээр хэл. Жишээ нь: «Миний inbox-ийг өдөр бүр цэвэрлэдэг самбар хийх».</span></li><li><b>2.</b><span>Agent асуулт асуувал хариул. Асуулгүйгээр код бичиж эхэлбэл «brainstorming skill-ээ ашигла» гэж хэл.</span></li><li><b>3.</b><span>Дизайныг уншаад «тийм» эсвэл «энийг өөрчил» гэж шийд. Эхний батлалт ингэж гарна.</span></li><li><b>4.</b><span>Төлөвлөгөөний жижиг даалгавар бүрийн дараа agent юу шалгасныг хүс. Командын гаралтыг хараад л «боллоо» гэ.</span></li></ol>
<div class="card box"><small>НЭГ ДҮРЭМ</small><p>Агентад «хий» гэхээсээ өмнө «эхлээд юу ойлгосноо бич» гэж хэл. Таамаглал ихэнхдээ тэнд л илэрнэ.</p></div>
<p>Энэ уншварын 10 слайдтай carousel хувилбар Instagram-д гарна. Хичээл 03-ын «Дараагийн үгийг таах машин» уншвар skill, session, repo гэсэн ойлголтыг дэлгэрэнгүй тайлбарласан тул хамт унших нь тохиромжтой.</p>
'''

head_end = s.find('<header class="ahead">')
art_start = s.find('<article class="abody">')
art_end = s.find('</article>')
out = s[:head_end]
out = re.sub(r"<title>.*?</title>", lambda m: f"<title>{TITLE} · itge.e</title>", out, flags=re.S)
out = re.sub(r'<meta name="description" content="[^"]*">', lambda m: f'<meta name="description" content="{DESC}">', out)
out = re.sub(r'<meta property="og:title" content="[^"]*">', lambda m: f'<meta property="og:title" content="{TITLE} · itge.e">', out)
out = re.sub(r'<meta property="og:description" content="[^"]*">', lambda m: f'<meta property="og:description" content="{DESC}">', out)
out = re.sub(r'<p class="crumb">[^<]*</p><a class="back" href="[^"]*">[^<]*</a>', '', out)
crumb = '<p class="crumb">Нийтлэл  ›  Season 2  ›  Хичээл 03</p><a class="back" href="../../lessons/03/index.html">← Хичээл 03</a>\n'
mid = s[head_end:art_start]
mid = re.sub(r'<h1>.*?</h1><p>.*?</p>', lambda m: f'<h1>{TITLE}</h1><p>{DEK}</p>', mid, count=1, flags=re.S)
mid = re.sub(r'<span>· [^<]*</span></div></header>', '<span>· 2026.10.29 · Skill · superpowers</span></div></header>', mid, count=1)
mid = re.sub(r'<img class="hero" src="[^"]*"', '<img class="hero" src="../../assets/img/skills-hero.jpg"', mid, count=1)
mid = re.sub(r'<div class="tagrow">.*?</div>\n', '', mid, flags=re.S)
rest = s[art_end:]
rel_start = rest.find('<h2 class="relh">')
rel_end = rest.find('<a class="btn dark sm"')
rel = ('<h2 class="relh">Холбоотой нийтлэл</h2><div class="relg">'
       '<a class="card rel" href="../../articles/daraagiin-ug/index.html"><div class="th"><img src="../../assets/img/th-daraagiin-ug.png" alt="" loading="lazy"><span class="tag light">ХИЧЭЭЛ 03</span></div><small>2026.10.27 · ИТГЭЛТӨГС Х.</small><b>Дараагийн үгийг таах машин</b><p>LLM яаж ажилладаг, сешн, repo, worktree, skill, workflow.</p></a>'
       '<a class="card rel" href="../../articles/bugdiig-neg-gazar/index.html"><div class="th"><img src="../../assets/img/th-bugdiig-neg-gazar.png" alt="" loading="lazy"><span class="tag light">ХИЧЭЭЛ 03</span></div><small>2026.10.29 · ИТГЭЛТӨГС Х.</small><b>Бүгдийг нэг газар цуглуулах</b><p>Inbox, нэг эх сурвалж.</p></a></div>')
rest = rest[:rel_start] + rel + rest[rel_end:]
page = out + crumb + mid + '<article class="abody">' + BODY + rest
(SITE / "articles/skills").mkdir(exist_ok=True)
(SITE / "articles/skills/index.html").write_text(page, encoding="utf-8")
print("articles/skills/index.html", len(page))
