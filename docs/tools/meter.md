# fm meter — PC нөөцийн хэмжүүр

Видео рендер, `npm run build`, Playwright зэрэг хүнд командыг ороож CPU, RAM, GPU, VRAM, дискийн бичилт, хугацааг хэмжиж монголоор тайлбарлана.

```bash
python plugins/fm/tools/meter/meter.py --label "inai build" [--note <vault note>] -- npm run build
```

- Командын гаралт шууд гарна, exit code нь дамжина.
- Үр дүн: `~/.fmos/meter/YYYY-MM-DD-HHMM-<label>.json` (дээж бүр + дүгнэлт).
- Ангилал: 🔴 хүнд (CPU дундаж ≥ 70%, GPU оргил ≥ 80%, VRAM ≥ 80%, RAM ≥ 85%, ≥ 10 мин) · 🟡 дунд (CPU дундаж ≥ 30% эсвэл оргил ≥ 90%, GPU дундаж ≥ 30%, RAM ≥ 70%, ≥ 60 сек) · 🟢 хөнгөн.
- Ижил label-ийн өмнөх хэмжүүртэй хугацааг харьцуулна; ажлын хавтасны дискэнд 20 GB-аас бага зай үлдвэл анхааруулна.
- `--note` → тэр note-ийн «Өөрчлөлтийн түүх» хүснэгтэд `resources:` мөр нэмнэ (зөвхөн нэмнэ).
- Хязгаар: RAM ба диск = систем бүхэлдээ (psutil-гүй, процессын мод биш); диск зөвхөн Windows (typeperf); GPU = nvidia-smi байвал; Mac дээр CPU = loadavg ойролцоо, RAM алгасна. 1 секундээс богино командад дээж авахгүй.
- Тест: `python tests/test_meter.py`.
