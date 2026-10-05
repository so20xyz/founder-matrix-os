## Юу өөрчилсөн бэ

<!-- 1–3 өгүүлбэр. Ямар skill / script / баримт. -->

## Яагаад

<!-- Ямар асуудлыг шийдэж байна. Issue байвал: Closes #123 -->

## Хэрхэн тестэлсэн

- [ ] `python3 .github/scripts/ci_checks.py` (test_hooks, test_onboard, test_doctor, test_tools, relay)
- [ ] `claude plugin validate --strict plugins/fm` ба `claude plugin validate --strict .`
- [ ] Туршилтын (жинхэнэ биш) vault дээр гараар шалгасан: <!-- юуг -->

OS: <!-- macOS / Windows / Linux -->  Python: <!-- python3 --version -->

## Шалгах жагсаалт

- [ ] Vault-ийн агуулга, token, нууц үг, харилцагчийн мэдээлэл, хувийн зам **ороогүй** (`git diff`-ээ харсан)
- [ ] Python 3.9-д ажиллана, цэвэр Python (bash/jq/pip сан шаардахгүй), Windows дээр ажиллана
- [ ] Хэрэглэгчид харагдах текст монголоор, skill/файлын нэр англи kebab-case
- [ ] Файлын мөрийн төгсгөлийг (LF/CRLF) өөрчлөөгүй
- [ ] Хувийн зүйл (finance, `private: true`) vault-аас гарахгүй хэвээр
- [ ] Шаардлагатай бол README / CHANGELOG шинэчилсэн
- [ ] `plugin.json`-ийн `version`-ийг өөрчлөөгүй (itge.e гаргахдаа нэмнэ)

- [ ] Албан ёсны skill-ийг хуулаагүй, гадны код/текст оруулаагүй

PR илгээснээр энэ хувь нэмрийн эрхийг [Founder Matrix License](../LICENSE)-ийн 4-р зүйлээр itge.e-д шилжүүлж байгаагаа, мөн илгээх эрхтэй гэдгээ баталж байна.
