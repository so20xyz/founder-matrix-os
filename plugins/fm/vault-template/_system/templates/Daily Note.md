---
date: <% tp.date.now("YYYY-MM-DD") %>
type: daily
tags:
  - daily
ai-first: true
focus: []          # {{fm:member}}-ийн оролт (дашбоардаас). ЖАГСААЛТ — mood/energy нь скаляр
mood:
energy:
habit_morning: false
habit_work: false
habit_learn: false
habit_move: false
habit_close: false
---

# <% tp.date.now("YYYY-MM-DD") %> - <% tp.date.now("dddd") %>

## For future agent

Daily note for this date. Captures what was worked on, who was met, decisions made, energy, and the day's intention. Pull this when reconstructing what happened on a given day.

---

## 🌅 Morning

**Intention:** <% tp.file.cursor() %>

**Grateful for:**
1.
2.
3.

---

## 🎯 Today's Focus

### 🔴 #1 -

### 🟡 #2 -

### 🟢 #3 -

---

## 💼 Work Log



---

## 🏠 Personal



---

## ✅ Habits

- [ ] Exercised
- [ ] Read/learned something
- [ ] Reached out to someone

---

## 🧠 Өнөөдрийн шийдвэрүүд

```dataview
TABLE WITHOUT ID decision AS "Шийдвэр", changetype AS "Төрөл", decidedby AS "Хэн", status AS "Төлөв"
FROM "04-Resources/Atomic"
WHERE type = "session-decision" AND dateformat(date, "yyyy-MM-dd") = this.file.name
SORT changetype ASC
```

---

## 🌙 Evening Review

**What went well:**

**What didn't:**

**Tomorrow's #1 priority:**
