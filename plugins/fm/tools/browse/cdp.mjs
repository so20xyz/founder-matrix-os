// cdp.mjs - Playwright connectOverCDP гацах үед (олон extension/worker target-тай жинхэнэ Chrome) ашиглах нимгэн raw CDP давхарга.
// /json/list-ээр target жагсааж, page-ийн webSocketDebuggerUrl руу Node 24-ийн global WebSocket-оор шууд ярина.
// Дүрэм: хэрэглэгчийн табыг хаахгүй, cookie/нэвтрэлтэд хүрэхгүй; зөвхөн өөрийн нээсэн табыг хаана.
const sleep = ms => new Promise(r => setTimeout(r, ms))

export class RawCDP {
  constructor(port) { this.base = `http://127.0.0.1:${port}`; this.opened = new Set() }
  async json(p, method = 'GET') {
    const r = await fetch(this.base + p, { method, signal: AbortSignal.timeout(8000) })
    if (!r.ok) throw new Error(`CDP ${p}: ${r.status}`)
    return r.json()
  }
  async pages() { return (await this.json('/json/list')).filter(t => t.type === 'page') }
  // шинэ таб (PUT /json/new) — өөрийн нээсэн гэж тэмдэглэнэ
  async newPage(url = 'about:blank') {
    const t = await this.json('/json/new?' + encodeURIComponent(url), 'PUT')
    this.opened.add(t.id)
    return this.attach(t)
  }
  async attach(t) { const pg = new RawPage(t, this); await pg.open(); return pg }
  async closeOwn(pg) {
    pg.ws?.close()
    if (this.opened.has(pg.id)) { await fetch(`${this.base}/json/close/${pg.id}`, { signal: AbortSignal.timeout(5000) }).catch(() => {}); this.opened.delete(pg.id) }
  }
}

export class RawPage {
  constructor(t, cdp) { this.id = t.id; this.wsUrl = t.webSocketDebuggerUrl; this.cdp = cdp; this.n = 0; this.wait = new Map(); this.events = [] }
  open() {
    return new Promise((ok, bad) => {
      const ws = this.ws = new WebSocket(this.wsUrl)
      const to = setTimeout(() => bad(new Error('CDP websocket холбогдсонгүй')), 8000)
      ws.onopen = () => { clearTimeout(to); ok() }
      ws.onerror = e => { clearTimeout(to); bad(new Error('CDP websocket алдаа')) }
      ws.onmessage = m => {
        const d = JSON.parse(typeof m.data === 'string' ? m.data : m.data.toString())
        if (d.id && this.wait.has(d.id)) { const { res, rej } = this.wait.get(d.id); this.wait.delete(d.id); d.error ? rej(new Error(d.error.message)) : res(d.result) }
        else if (d.method) this.events.push(d.method)
      }
    })
  }
  send(method, params = {}, ms = 30000) {
    const id = ++this.n
    return new Promise((res, rej) => {
      const to = setTimeout(() => { this.wait.delete(id); rej(new Error(method + ' хугацаа хэтэрсэн')) }, ms)
      this.wait.set(id, { res: v => { clearTimeout(to); res(v) }, rej: e => { clearTimeout(to); rej(e) } })
      this.ws.send(JSON.stringify({ id, method, params }))
    })
  }
  async evaluate(expression, { awaitPromise = true, returnByValue = true } = {}) {
    const r = await this.send('Runtime.evaluate', { expression, awaitPromise, returnByValue })
    if (r.exceptionDetails) throw new Error('evaluate: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text))
    return r.result.value
  }
  async navigate(url, waitLoad = true, ms = 30000) {
    await this.send('Page.navigate', { url })
    if (!waitLoad) return
    const t0 = Date.now(); await sleep(300)
    while (Date.now() - t0 < ms) { if (await this.evaluate('document.readyState').catch(() => '') !== 'loading') return; await sleep(300) }
  }
  async waitFor(selector, ms = 30000) {
    const t0 = Date.now()
    while (Date.now() - t0 < ms) { if (await this.evaluate(`!!document.querySelector(${JSON.stringify(selector)})`).catch(() => false)) return; await sleep(500) }
    throw new Error('selector олдсонгүй: ' + selector)
  }
  async url() { return this.evaluate('location.href') }
  async screenshot({ width, fullPage = true } = {}) {
    if (width) {
      const h = fullPage ? await this.evaluate('document.documentElement.scrollHeight') : 900
      await this.send('Emulation.setDeviceMetricsOverride', { width, height: Math.ceil(h), deviceScaleFactor: 1, mobile: false })
    }
    const r = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: fullPage })
    return Buffer.from(r.data, 'base64')
  }
}
