# dom2fig — вэб компонент → бодит Figma давхарга

```bash
npm i playwright-core   # тусдаа хавтсанд
node dump.mjs <slug> "<selector>" out/<slug>.json           # DOM → JSON + out/<slug>.png (лавлах)
python ../fig.py -d "<файл>" run -f build.js --inject TREE=out/<slug>.json --inject META=meta.json -t 180
python ../fig.py -d "<файл>" export <id> --out fexp/<slug>.png
python diff.py fexp out review   # review/diff.json + review/sheets/*.png (studio | figma)
```

- `dump.mjs`: URL = env `BASE` + slug (анхдагч thinkstate.site/#/). `SETTLE` (ms) — анимацийн төгсгөл хүлээх.
- `build.js`: META `{slug, name, page}` (page = хуудасны id); section нэр, «Studio tokens» Variables-ийг файл дотроо засна.
- Дүрэм: `skills/figma/SKILL.md` → «Код → бодит Figma давхарга».
