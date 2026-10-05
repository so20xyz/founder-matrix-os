// Framer Bridge — CLI (fr.py) → localhost:3056 сервер → энэ plugin → framer API. Figma bridge-ийн хос.
import { framer } from "@framer/plugin"
import { useEffect, useState } from "react"
import "./App.css"

framer.showUI({ position: "bottom right", width: 260, height: 120 })
const SRV = "https://localhost:5173/bridge"
const AsyncFn = Object.getPrototypeOf(async function () {}).constructor

export function App() {
  const [log, setLog] = useState<string[]>([])
  const [ok, setOk] = useState(false)
  useEffect(() => {
    let alive = true
    const add = (s: string) => setLog(l => [s, ...l].slice(0, 6))
    ;(async () => {
      const info = await framer.getProjectInfo()
      const file = info.name
      while (alive) {
        try {
          const r = await fetch(`${SRV}/next?file=${encodeURIComponent(file)}`)
          setOk(true)
          if (r.status !== 200) continue
          const job = await r.json()
          add("▶ " + (job.title || job.id))
          let out
          try {
            const res = await new AsyncFn("framer", "log", job.code)(framer, (m: string) => add(String(m)))
            out = { id: job.id, ok: true, result: res === undefined ? null : JSON.parse(JSON.stringify(res, (_k, v) => typeof v === "bigint" ? String(v) : v)) }
          } catch (e: any) {
            out = { id: job.id, ok: false, error: String(e?.stack || e) }
            add("✗ " + String(e?.message || e).slice(0, 80))
          }
          await fetch(`${SRV}/result`, { method: "POST", body: JSON.stringify(out) })
        } catch (e: any) {
          setOk(false); add("net: " + String(e?.message || e).slice(0, 90))
          await new Promise(r => setTimeout(r, 2000))
        }
      }
    })()
    return () => { alive = false }
  }, [])
  return (
    <main style={{ fontSize: 11, padding: 8 }}>
      <b>{ok ? "● Bridge холбогдсон" : "○ Сервер хүлээж байна (node server.mjs)"}</b>
      {log.map((l, i) => <div key={i} style={{ opacity: 0.7 }}>{l}</div>)}
    </main>
  )
}
