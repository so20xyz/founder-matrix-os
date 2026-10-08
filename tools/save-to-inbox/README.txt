# Save to Inbox - Obsidian vault

Chrome/Brave/Edge extension. Одоогийн вэб хуудсыг **шууд** Obsidian vault-ийн `02-GTD/inbox/` руу reference болгон хадгална. Notion-оор дамжихгүй.

## Хэрхэн ажилладаг (2 горим)

1. **Local REST API (санал болгож буй - Obsidian урд гарахгүй):** Obsidian "Local REST API" plugin суулгаж, extension-ий Options-д API key оруулбал extension нь localhost руу HTTP бичнэ. **Фокус солихгүй**, урт нийтлэл ч бүрэн орно.
2. **obsidian:// fallback:** API key байхгүй бол `obsidian://new` URI (Obsidian урд гарна).

Аль ч горимд нот `02-GTD/inbox/clip - <гарчиг>-<цаг>.md` болж, Command Center 📥 Inbox таб-д гарна.

## Суулгах (2 минут)

1. Chrome (эсвэл Brave/Edge)-д `chrome://extensions` нээ
2. Баруун дээд булангийн **Developer mode**-ыг асаа
3. **Load unpacked** дар → энэ хавтасыг сонго: `<repo>/tools/save-to-inbox`
4. Toolbar дээр 📥 icon гарч ирнэ (pin хийж болно)

## Ашиглах

1. Хадгалмаар хуудсан дээрээ 📥 icon дар
2. Гарчиг/төрөл/төсөл/тэмдэглэл шалгаад (сонголтоор текст сонгосон бол автоматаар орно)
3. **Vault Inbox руу хадгалах** дар
4. Эхний удаа Chrome «Obsidian нээх үү?» гэж асууна → **зөвшөөр** (Always allow)

## Тохиргоо

- Extension-ий **Options**-д vault-ийнхаа **нэр**-ийг бич. Ижил нэртэй хоёр vault байвал Obsidian-ий **vault ID** (Obsidian → Manage vaults) бич — тэгвэл буруу vault руу орохгүй.
- Obsidian **нээлттэй** байх ёстой (хаалттай бол URI ажиллахгүй).
- Frontmatter: `type: reference`, `status: draft`, `source: web-clip`, `reftype`, `url`, `related-projects`. AI-first цэвэр (em-dash/curly quote автоматаар ASCII болгодог).

## Фокус солихгүй болгох (Local REST API тохиргоо)

Extension icon дээр **баруун товш → Options** (эсвэл chrome://extensions → Details → Extension options). Тэнд:

1. Obsidian → Settings → Community plugins → **Local REST API** суулга, идэвхжүүл
2. Local REST API тохиргоонд **Enable Non-encrypted (HTTP) Server** асаа (порт 27123)
3. **API Key**-г хуулж Options-д тавь → Хадгалах

Дараа нь хадгалахад Obsidian **урд гарахгүй** шууд бичнэ. API key тохируулаагүй бол хуучин `obsidian://` аргаар (Obsidian урд гарна) ажилласаар байна - regression байхгүй.
