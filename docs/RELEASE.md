# Release ба issue triage

founder-matrix-os нь Monton 1-1 болон Second Brain Season 2-ын эх сурвалж (itge.e 2026-11-04). Өөрчлөлт бүр гишүүний машинд хүрдэг тул release-ийн дүрэм хүний толгойд биш, энд ба скриптэд амьдарна. **Шалгалт автомат, push-ийн шийдвэр хүнийх.** CI, сервер байхгүй — бүгд локал скрипт (гишүүд Windows дээр).

## Release

1. `plugins/fm/`-д өөрчлөлт хийсэн бол `plugins/fm/.claude-plugin/plugin.json`-ийн `version`-ийг өсгө (SemVer). Version өсөхгүй бол `claude plugin update fm` шинэ кодыг **татахгүй** (2026-11-04: `fm_loop` 3f8f40f-д орсон ч гишүүдэд хүрээгүй).
2. `CHANGELOG.md`-д `## fm X.Y.Z · YYYY-MM-DD · <гарчиг>` бичилт нэм.
3. Push-ийн өмнөх шалгалт:

   ```
   python3 plugins/fm/scripts/fm_release_check.py "<maintainer vault>"
   ```

   | # | Шалгалт | Унавал |
   |---|---|---|
   | 1 | version өссөн (`plugins/fm` origin/main-аас өөрчлөгдсөн бол) | plugin.json-ийг өсгө |
   | 2 | CHANGELOG-д тэр хувилбар бий | бичилт нэм |
   | 3 | `fm_rules.py export`, `fm_bases.py export` хүлээгдэж буй өөрчлөлтгүй | `… export <vault> --apply`. ⚠ = загварыг гараар ерөнхийлж vault-аас шинэ болгосон файл, хүн шалгана |
   | 4 | `vault-template` дээр `fm_loop` 5/5 ❌ (эсрэг туршилт) | загварт амьд өгөгдөл орсон эсвэл шалгуур зөөлөрсөн |

   Нэг ч ❌ байвал release зогсоно. Тест: `python3 tests/<test>.py`.
4. **Push** — хүн шийднэ.
5. Push-ийн дараа: `python3 plugins/fm/scripts/fm_release_check.py "<vault>" --pushed` → `git ls-remote origin main` == локал HEAD.

## Гишүүний upgrade-ийн зам

```
claude plugin marketplace update founder-matrix
claude plugin update fm@founder-matrix
```

Claude-аа бүрэн хааж дахин нээ → `/fm:setup sync` (repo, sidebar, дүрэм нөхөх) → `python3 "<plugin>/scripts/fm_loop.py" "<vault>"` (гинж бүрэн эсэх). Season 2 / Monton downstream repo-гийн гишүүд өөрийн marketplace-аа (`second-brain-season-2`, `orgio-second-brain`) шинэчилнэ — тэдгээр нь `fm_downstream.py`-аар энэ repo-оос шүүж синк хийгддэг.

## Issue triage

| Шошго | Хэзээ |
|---|---|
| `bug` | Ажиллах ёстой зүйл эвдэрсэн (алхам, алдааны мөр хавсарга) |
| `enhancement` | Шинэ боломж, горим |
| `documentation` | README, GUIDE, SKILL-ийн бичвэр |
| `question` | Хэрэглээний асуулт — хариулаад хаана |
| `duplicate` | Өмнөх issue-гийн холбоосыг бичээд хаана |
| `wontfix` / `invalid` | Шалтгааныг нэг өгүүлбэрээр бичээд хаана |

- **Хариулах хугацаа (itge.e баталсан, 2026-11-04):** гишүүний issue-д **2 ажлын өдрийн дотор анхны хариу** — шошго тавьж, дараагийн алхмыг нэрлэнэ. Анхны хариу нь шийдэл байх шаардлагагүй, харин «хэн, хэзээ, юу» гэдэг нь тодорхой байна. Bug-ийг дараагийн release-д авах эсвэл `someday` гэж тодорхой хэлнэ — хариугүй орхихгүй.
- **Давхардал:** нээхийн өмнө `gh issue list --search "<түлхүүр үг>"`; давхардсан бол шинийг `duplicate` болгож хуучинд нь холбоно.
- **Хувийн мэдээлэл:** issue-д үйлчлүүлэгчийн нэр, санхүү, хувийн зам бүү бич (repo private ч гишүүд уншина).
- Issue бүр vault-д `01-GTD/Tasks/`-ийн task-тай хоёр талдаа холбогдоно (task-д issue URL, issue-д шийдвэрийн атом).
