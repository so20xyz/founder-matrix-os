# Бичлэг үзэх — `/fm:watch`

| | |
|---|---|
| **Юу** | YouTube/Instagram/TikTok линк эсвэл локал файлыг татаж: транскрипт (txt/srt/json), N секунд тутмын кадрын хуудас (`sheet.jpg`), мета (`meta.json`). Claude кадруудыг харж, текстийг уншаад дүгнэнэ |
| **Агент** | Research, Resource (лавлагаа + атом), Creative (жишээ задлах) |
| **Код** | `plugins/fm/tools/watch/watch.py` (Mac + Windows, pure Python) |
| **Шаардлага** | ffmpeg (заавал), yt-dlp (линк), uv (транскрипт) — `python3 plugins/fm/scripts/fm_doctor.py --only ffmpeg,yt-dlp,uv` |
| **Token** | Хэрэггүй |

## Транскрипт (заавал биш)

| Engine | Хаана | Тайлбар |
|---|---|---|
| `mlx` | Apple Silicon Mac | mlx-whisper, локал, хурдан. Эхний удаа ~1.6 GB загвар |
| `faster` | Mac / Windows / Linux | faster-whisper, CPU, удаан |
| `none` | хаана ч | зөвхөн кадр + мета |

`--engine auto` (анхдагч) Apple Silicon бол `mlx`, бусад үед `faster`; uv алга бол транскриптгүй. Монгол бичлэгт `--lang mn`.

## Суулгах (Mac)

```
brew install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install yt-dlp
```

Windows: `winget install --id Gyan.FFmpeg -e`, uv (`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`), `uv tool install yt-dlp`. fm_doctor эдгээрийг таны зөвшөөрлөөр санал болгоно.

Гаралт: `~/.cache/fm-watch/<нэр>/` (Windows: `%LOCALAPPDATA%\fm-watch\<нэр>\`). Хадгалах бол `/fm:save <url>`.
