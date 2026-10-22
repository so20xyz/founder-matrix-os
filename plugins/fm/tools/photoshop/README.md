# Photoshop CLI (ps.py)

Photoshop-ийг терминалаас удирдах хэрэгсэл. Premiere-ийн гүүр (bridge) шиг ажилладаг ч CEP панел, порт шаарддаггүй: Windows-ийн COM объект (`Photoshop.Application`) дээрх `DoJavaScript`-ийг PowerShell-ээр дуудаж, ExtendScript ажиллуулна. pywin32 суулгах шаардлагагүй, зөвхөн Python-ийн стандарт сан.

## Командууд

```
python ps.py status                               Photoshop ажиллаж байгаа эсэх, хувилбар, нээлттэй баримтууд
python ps.py layers [--doc NAME]                  давхаргын мод (нэр, төрөл, харагдах эсэх, хүрээ) JSON-оор
python ps.py run -f script.jsx [--doc NAME]       дурын ExtendScript; сүүлийн утга эсвэл __result JSON болж буцна
python ps.py run -e "app.documents.length"        мөрөнд шууд бичсэн скрипт
python ps.py export active --out F.png [--scale 0.5] [--format png|jpg] [--quality 10]
python ps.py action "Default Actions" "Vignette"  action тоглуулах
python ps.py open PATH                            файл нээх
python ps.py new --w 1080 --h 1350 [--name N]     шинэ баримт
```

Гаралт бүр `{"ok": true, "result": ...}` эсвэл `{"ok": false, "error": ...}` хэлбэртэй.

## Дүрэм

- Photoshop ажиллаагүй бол ps.py түүнийг дуугүй асаахгүй. Асаах шаардлагатай бол `--launch` нэм.
- Хэрэглэгчийн баримтыг хэзээ ч хадгалахгүй, хаахгүй. `export` нь баримтын хуулбар (duplicate) үүсгэж, хуулбарыг хадгалаад хаадаг тул эх баримт хөндөгдөхгүй.
- Кирилл зам, бичвэр: скриптийг UTF-8 түр файлд бичиж, PowerShell `[System.IO.File]::ReadAllText`-ээр уншина; JS доторх мөрүүд ASCII-аюулгүй `\u` хэлбэрээр ордог.
- `run` скриптэд `FM.doc(name)`, `FM.docInfo(d)`, `FM.layers(d)`, `FM.px(unit)` туслах функц бэлэн.
- Premiere-ийн сургамж: `while` гогцоонд дахин дахин бүү дууд, нэг скриптэд багцалж ажиллуул.

## Тест

`python tests/test_photoshop_ps.py` — JS ороолт, аргумент задлалт, PowerShell скрипт (Photoshop шаардлагагүй).
