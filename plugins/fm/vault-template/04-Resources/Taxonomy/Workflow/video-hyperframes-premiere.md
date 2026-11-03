---
type: taxonomy
axis: workflow
value: video-hyperframes-premiere
label: "HyperFrames → Premiere видео"
icon: "🎬"
trigger: "Reel-ийн график блок хэрэгтэй болно"
steps:
  - n: 1
    do: "HyperFrames composition бэлдэж блокийг ProRes 4444 alpha-аар рендерлэнэ"
    skill: null
    agent: creative
    tool: codebase
  - n: 2
    do: "Premiere гүүрээр sequence-д импортлож байрлуулна, шалгана"
    skill: superpowers-verification-before-completion
    agent: architect
    tool: premiere
  - n: 3
    do: "Текст, SFX, аудиог Premiere-ийн дотоод хэрэгслээр хийнэ"
    skill: null
    agent: creative
    tool: premiere
  - n: 4
    do: "SOP-г шинэчилж лог бичнэ"
    skill: fm-log
    agent: wiki
    tool: null
outputs:
  - "HyperFrames блок (.mov, alpha)"
  - "Premiere sequence дээрх reel"
example: "[[01-GTD/Tasks/Видео - Видео урсгалын SOP-г Reel засвар note-д нэгтгэх]]"
aliases: []
date: 2026-10-25
tags: [taxonomy, workflow]
ai-first: true
up: "[[04-Resources/Taxonomy/Ангилал]]"
status: active
---
# 🎬 HyperFrames → Premiere видео

**Тэнхлэг:** `workflow:` — олон алхам, дүр солигдох, батлах цэгтэй нэрлэсэн урсгал. @mention: `@video-hyperframes-premiere`.

## Юу вэ
Бөөн рендер биш: зөвхөн график блокийг HyperFrames-ээр, бусдыг Premiere-д.

## Эхлүүлэгч
Reel-ийн график блок хэрэгтэй болно.

## Алхмууд
1. HyperFrames composition бэлдэж блокийг ProRes 4444 alpha-аар рендерлэнэ — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `creative` · хэрэгсэл: `codebase`
2. Premiere гүүрээр sequence-д импортлож байрлуулна, шалгана — skill: `@superpowers-verification-before-completion` · дүр: `architect` · хэрэгсэл: `premiere`
3. Текст, SFX, аудиог Premiere-ийн дотоод хэрэгслээр хийнэ — skill-гүй (хүний эсвэл системийн үйлдэл) · дүр: `creative` · хэрэгсэл: `premiere`
4. SOP-г шинэчилж лог бичнэ — skill: `@fm-log` · дүр: `wiki`

## Гаралт
- HyperFrames блок (.mov, alpha)
- Premiere sequence дээрх reel

## Жишээ
[[01-GTD/Tasks/Видео - Видео урсгалын SOP-г Reel засвар note-д нэгтгэх]]

## Дуудах
Task-д `workflow: video-hyperframes-premiere`, чатад `@video-hyperframes-premiere`.
