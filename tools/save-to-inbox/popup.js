// Save to Inbox - Obsidian vault-iin 02-GTD/inbox ruu hadgalna.
// Ded 1 (heregtei): Obsidian "Local REST API" plugin asaasan bol localhost ruu HTTP
//   bичдег => Obsidian NEEGDDEGGUI (fokus solihgui), urt niitlel ч buten orno.
// Ded 2 (fallback): API key togiruulaagui bol obsidian://new URI (Obsidian urd garna).
// Vault: Options-д тохируулна (нэр эсвэл Obsidian vault ID). obsidian:// fallback-д л хэрэглэгдэнэ.
const DEFAULT_ENDPOINT = "http://127.0.0.1:27123";

function clean(s) {
  return String(s == null ? "" : s)
    .replace(/[—–]/g, " - ")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/…/g, "...")
    .replace(/≤/g, "<=")
    .replace(/≥/g, ">=")
    .replace(/≠/g, "!=")
    .replace(/ /g, " ");
}
function slug(s) {
  return (clean(s) || "clip").toLowerCase()
    .replace(/[^a-z0-9Ѐ-ӿ]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "clip";
}
function pad(n) { return String(n).padStart(2, "0"); }

async function currentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}
async function getSelection(tabId) {
  try {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => String(window.getSelection ? window.getSelection() : "")
    });
    return (res && res[0] && res[0].result) ? res[0].result : "";
  } catch (e) { return ""; }
}
// Inbox-ийн зам: шинэ 02-GTD/inbox; vault-д байхгүй ч хуучин 00-Inbox байвал түүнийг (шилжилтийн хамгаалалт).
const INBOX_NEW = "02-GTD/inbox", INBOX_OLD = "00-Inbox";
async function inboxDir(apiKey, endpoint) {
  if (!apiKey) return INBOX_NEW;
  const ls = async (d) => {
    try {
      const r = await fetch(`${endpoint}/vault/${encodeURI(d + "/")}`, { headers: { "Authorization": "Bearer " + apiKey } });
      return r.ok;
    } catch (e) { return null; }
  };
  const hasNew = await ls(INBOX_NEW);
  if (hasNew === false && (await ls(INBOX_OLD)) === true) return INBOX_OLD;
  return INBOX_NEW;
}

function getCfg() {
  return new Promise((res) => {
    try {
      chrome.storage.local.get(["apiKey", "endpoint", "vault"], (d) =>
        res({ apiKey: (d && d.apiKey) || "", endpoint: (d && d.endpoint) || DEFAULT_ENDPOINT, vault: (d && d.vault) || "" }));
    } catch (e) { res({ apiKey: "", endpoint: DEFAULT_ENDPOINT, vault: "" }); }
  });
}

let SHOT = ""; // scaled JPEG data URL of the page screenshot

function dataUrlToBytes(dataUrl) {
  const b64 = (dataUrl || "").split(",")[1] || "";
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}

async function captureThumb() {
  try {
    const dataUrl = await new Promise((res, rej) => {
      chrome.tabs.captureVisibleTab(null, { format: "jpeg", quality: 85 }, (u) => {
        if (chrome.runtime.lastError || !u) rej(chrome.runtime.lastError || new Error("no capture")); else res(u);
      });
    });
    const img = new Image();
    await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = dataUrl; });
    const maxW = 900;
    const scale = Math.min(1, maxW / (img.width || maxW));
    const cv = document.createElement("canvas");
    cv.width = Math.max(1, Math.round((img.width || maxW) * scale));
    cv.height = Math.max(1, Math.round((img.height || 1) * scale));
    cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
    SHOT = cv.toDataURL("image/jpeg", 0.7);
    const el = document.getElementById("thumb");
    const wrap = document.getElementById("thumbwrap");
    if (el) el.src = SHOT;
    if (wrap) wrap.style.display = "block";
  } catch (e) { SHOT = ""; }
}

let MEDIA = { site: "generic", images: [], ogVideo: "" };

async function extractMedia(tabId) {
  try {
    const res = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const meta = (n) => { const el = document.querySelector(`meta[property="${n}"], meta[name="${n}"]`); return el ? el.content : ""; };
        const abs = (u) => { try { return new URL(u, location.href).href; } catch (e) { return u || ""; } };
        const host = location.hostname.replace(/^www\./, "");
        let site = "generic";
        if (/pinterest\./.test(host)) site = "pinterest";
        else if (/instagram\.com/.test(host)) site = "instagram";
        else if (/(^|\.)(twitter|x)\.com/.test(host)) site = "twitter";
        else if (/youtube\.com|youtu\.be/.test(host)) site = "youtube";
        else if (/tiktok\.com/.test(host)) site = "tiktok";
        const byKey = new Map(); // origin+pathname -> url (ижил зургийн олон хэмжээг нэгтгэнэ)
        const keyOf = (u) => { try { const x = new URL(u); return x.origin + x.pathname; } catch (e) { return u; } };
        const add = (u) => {
          u = abs(u);
          if (!u || !/^https?:/.test(u) || /\.svg($|\?)/i.test(u)) return;
          if (/emoji|sprite|avatar|profile_pic|favicon|badge|/i.test(u) && /avatar|profile_pic|favicon|emoji|sprite/i.test(u)) return;
          const k = keyOf(u); if (!byKey.has(k)) byKey.set(k, u);
        };
        const srcOf = (im) => {
          let best = im.currentSrc || im.src || "";
          if (im.srcset) { const parts = im.srcset.split(",").map(s => s.trim().split(/\s+/)); const last = parts[parts.length - 1]; if (last && last[0]) best = last[0]; }
          return best;
        };
        const og = abs(meta("og:image") || meta("twitter:image"));
        if (og) add(og);
        if (site === "pinterest") {
          const cl = document.querySelector('[data-test-id="pin-closeup-image"] img, [data-test-id="closeup-image"] img, [data-test-id="visual-content-container"] img, [data-test-id="pin-image"] img');
          if (cl) add(srcOf(cl)); // зөвхөн pin, related pins биш
        } else if (site === "instagram") {
          const art = document.querySelector("article"); // зөвхөн эхний пост, санал болгосон биш
          if (art) art.querySelectorAll("img").forEach(im => { const s = srcOf(im); if ((im.naturalWidth || 0) >= 320 || /scontent|cdninstagram/.test(s)) add(s); });
        } else if (site === "twitter") {
          const art = document.querySelector('article[data-testid="tweet"]') || document.querySelector("article") || document;
          art.querySelectorAll('img[src*="twimg.com/media"]').forEach(im => add((im.src || "").replace(/&name=\w+/, "&name=large")));
        } else {
          const root = document.querySelector("article") || document.querySelector("main") || document.body;
          root.querySelectorAll("img").forEach(im => { if ((im.naturalWidth || im.width || 0) >= 400) add(srcOf(im)); });
        }
        const ogVideo = abs(meta("og:video:secure_url") || meta("og:video:url") || meta("og:video"));
        let videoPage = "";
        if (site === "youtube" || /vimeo\.com/.test(host)) videoPage = location.href;
        let videoFile = "";
        const vEl = document.querySelector("video");
        const vSrc = vEl ? (vEl.currentSrc || vEl.src || (vEl.querySelector("source") && vEl.querySelector("source").src) || "") : "";
        const vc = [vSrc, ogVideo].map(abs).find(u => /\.(mp4|webm|mov)(\?|$)/i.test(u || ""));
        if (vc) videoFile = vc;
        const cleanT = (t) => (t || "")
          .replace(/^\(\d+\)\s*/, "")
          .replace(/\s*[|•·\-–—:]\s*(Instagram|Pinterest|YouTube|TikTok|X|Twitter|Facebook|Reddit)(\s*\(formerly Twitter\))?\s*$/i, "")
          .replace(/\s+/g, " ").trim();
        const siteName = /^(instagram|pinterest|tiktok|youtube|twitter|x|facebook|reddit|linkedin)$/i;
        let title = "";
        for (const cand of [meta("og:title"), meta("twitter:title"), document.title, meta("og:description"), meta("twitter:description")]) {
          const c = cleanT(cand);
          if (c && c.length >= 3 && !siteName.test(c)) { title = c; break; }
        }
        if (!title) {
          const im = document.querySelector('[data-test-id="pin-closeup-image"] img[alt], [data-test-id="visual-content-container"] img[alt], article img[alt], main img[alt], img[alt]');
          if (im && im.alt) { const a = cleanT(im.alt); if (a.length >= 3) title = a; }
        }
        if (!title) title = cleanT(meta("og:title") || document.title) || "clip";
        title = title.slice(0, 90);
        let embedHtml = "";
        if (site === "instagram") {
          const m = location.href.match(/instagram\.com\/(reel|reels|p|tv)\/([^/?#]+)/i);
          if (m) { const kind = m[1] === "reels" ? "reel" : m[1]; embedHtml = `<iframe src="https://www.instagram.com/${kind}/${m[2]}/embed" width="400" height="505" frameborder="0" scrolling="no" allowtransparency="true"></iframe>`; }
        } else if (site === "tiktok") {
          const m = location.href.match(/tiktok\.com\/@[^/]+\/video\/(\d+)/i);
          if (m) embedHtml = `<iframe src="https://www.tiktok.com/embed/v2/${m[1]}" width="325" height="575" frameborder="0" scrolling="no" allow="encrypted-media"></iframe>`;
        }
        return { site, title, images: Array.from(byKey.values()).slice(0, 12), ogVideo, videoPage, videoFile, embedHtml };
      }
    });
    if (res && res[0] && res[0].result) MEDIA = res[0].result;
  } catch (e) { MEDIA = { site: "generic", images: [], ogVideo: "" }; }
  return MEDIA;
}

let SELECTED = new Set();

function updateSelCount() {
  const c = document.getElementById("selCount");
  if (c) c.textContent = SELECTED.size ? `${SELECTED.size} сонгосон` : "сонгоогүй";
  document.querySelectorAll("#gallery .gcell").forEach((cell) => {
    const i = +cell.getAttribute("data-i");
    const on = SELECTED.has(i);
    cell.style.outline = on ? "3px solid var(--interactive-accent,#5B3E8C)" : "3px solid transparent";
    cell.style.opacity = on ? "1" : "0.5";
    const bd = cell.querySelector(".gbadge");
    if (bd) bd.style.display = on ? "flex" : "none";
  });
}

function renderGallery() {
  const wrap = document.getElementById("mediawrap");
  const g = document.getElementById("gallery");
  const cnt = document.getElementById("mediacount");
  SELECTED = new Set();
  if (!MEDIA.images.length) { if (wrap) wrap.style.display = "none"; return; }
  if (cnt) cnt.textContent = `(${MEDIA.site} · ${MEDIA.images.length})`;
  if (g) {
    g.innerHTML = "";
    MEDIA.images.forEach((u, i) => {
      const cell = document.createElement("div");
      cell.className = "gcell";
      cell.setAttribute("data-i", String(i));
      cell.style.cssText = "position:relative;flex:0 0 auto;border-radius:8px;cursor:pointer;outline:3px solid transparent;line-height:0";
      const im = document.createElement("img");
      im.src = u; im.loading = "lazy";
      im.style.cssText = "height:72px;width:auto;border-radius:6px;display:block";
      const badge = document.createElement("div");
      badge.className = "gbadge";
      badge.textContent = "✓";
      badge.style.cssText = "position:absolute;top:3px;right:3px;width:18px;height:18px;border-radius:50%;background:var(--interactive-accent,#5B3E8C);color:#fff;font-size:12px;display:none;align-items:center;justify-content:center";
      cell.appendChild(im); cell.appendChild(badge);
      cell.addEventListener("click", () => { if (SELECTED.has(i)) SELECTED.delete(i); else SELECTED.add(i); updateSelCount(); });
      g.appendChild(cell);
    });
  }
  SELECTED.add(0); // default: эхний (үндсэн) зураг сонгосон
  updateSelCount();
  if (wrap) wrap.style.display = "block";
}

function renderVideo() {
  const wrap = document.getElementById("videowrap");
  const info = document.getElementById("videoinfo");
  const dlwrap = document.getElementById("vdlwrap");
  if (!MEDIA.videoPage && !MEDIA.videoFile && !MEDIA.embedHtml) { if (wrap) wrap.style.display = "none"; return; }
  if (info) info.textContent = MEDIA.embedHtml ? "(IG/TikTok - Obsidian дотор iframe-ээр тоглоно)" : (MEDIA.videoPage ? "(YouTube/Vimeo - Obsidian embed тоглуулна)" : "(шууд файл - татаж болно)");
  if (dlwrap) dlwrap.style.display = MEDIA.videoFile ? "flex" : "none";
  if (wrap) wrap.style.display = "block";
}

async function saveImage(url, apiKey, endpoint, name) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("fetch " + r.status);
  const buf = await r.arrayBuffer();
  let ext = (url.split("?")[0].match(/\.(jpe?g|png|webp|gif)$/i) || [])[1];
  ext = (ext || "jpg").toLowerCase().replace("jpeg", "jpg");
  const ctype = ext === "jpg" ? "image/jpeg" : "image/" + ext;
  const fn = `${name}.${ext}`;
  const pr = await fetch(`${endpoint}/vault/${encodeURI("_system/attachments/" + fn)}`, {
    method: "PUT",
    headers: { "Authorization": "Bearer " + apiKey, "Content-Type": ctype },
    body: buf
  });
  if (!pr.ok) throw new Error("put " + pr.status);
  return fn;
}

let TAB = null;
(async () => {
  TAB = await currentTab();
  document.getElementById("title").value = clean(TAB && TAB.title ? TAB.title : "");
  document.getElementById("url").textContent = (TAB && TAB.url) ? TAB.url : "";
  await extractMedia(TAB && TAB.id);
  if (MEDIA.title) document.getElementById("title").value = clean(MEDIA.title); // og:title > tab title
  renderGallery();
  renderVideo();
  if (!MEDIA.images.length) captureThumb(); // контент зураг олдоогүй бол screenshot fallback
})();
const reshotBtn = document.getElementById("reshot");
if (reshotBtn) reshotBtn.addEventListener("click", captureThumb);
const selAllEl = document.getElementById("selAll");
if (selAllEl) selAllEl.addEventListener("click", (e) => { e.preventDefault(); MEDIA.images.forEach((_, i) => SELECTED.add(i)); updateSelCount(); });
const selNoneEl = document.getElementById("selNone");
if (selNoneEl) selNoneEl.addEventListener("click", (e) => { e.preventDefault(); SELECTED.clear(); updateSelCount(); });

document.getElementById("save").addEventListener("click", async () => {
  const btn = document.getElementById("save");
  const ok = document.getElementById("ok");
  btn.disabled = true;
  const url = (TAB && TAB.url) ? TAB.url : "";
  const title = clean(document.getElementById("title").value) || "clip";
  const reftype = document.getElementById("reftype").value || "website";
  const project = clean(document.getElementById("project").value).trim();
  const note = clean(document.getElementById("note").value).trim();
  const claudeTask = clean(document.getElementById("claudeTask").value).trim();
  const sel = clean(await getSelection(TAB && TAB.id));

  const d = new Date();
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const stamp = `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  const base = `clip - ${slug(title)}-${stamp}`;

  const { apiKey, endpoint } = await getCfg();

  // --- Медиа: сайт-тусгай контент зураг (Pinterest pin, carousel, IG) > screenshot ---
  const chosen = MEDIA.images.filter((_, i) => SELECTED.has(i));
  const embeds = [];       // markdown embed мөрүүд
  let thumbFront = "";     // frontmatter thumbnail утга
  if (chosen.length) {
    for (let i = 0; i < chosen.length; i++) {
      const u = chosen[i];
      if (apiKey) {
        try {
          const fn = await saveImage(u, apiKey, endpoint, `clip-${stamp}-${i + 1}`);
          embeds.push(`![[${fn}]]`);
          if (!thumbFront) thumbFront = `"[[${fn}]]"`;
          continue;
        } catch (e) { /* татаж чадсангүй -> URL-ээр embed */ }
      }
      embeds.push(`![](${u})`);
      if (!thumbFront) thumbFront = `"${u}"`;
    }
  } else if (SHOT && apiKey) {
    try {
      const fn = `clip-${stamp}.jpg`;
      const ri = await fetch(`${endpoint}/vault/${encodeURI("_system/attachments/" + fn)}`, {
        method: "PUT", headers: { "Authorization": "Bearer " + apiKey, "Content-Type": "image/jpeg" }, body: dataUrlToBytes(SHOT)
      });
      if (ri.ok) { embeds.push(`![[${fn}]]`); thumbFront = `"[[${fn}]]"`; }
    } catch (e) {}
  }

  const rel = project ? `\n  - "[[${project}]]"` : " []";
  const lines = [
    "---",
    `date: ${date}`,
    "type: reference",
    "status: draft",
    "tags:", "  - reference", "  - inbox", "  - web-clip",
    `reftype: ${reftype}`,
    `url: "${url}"`,
    "source: web-clip",
    ...(thumbFront ? [`thumbnail: ${thumbFront}`] : []),
    `related-projects:${rel}`,
    ...(claudeTask ? ["needs-claude: true"] : []),
    "ai-first: true",
    "---",
    "",
    "## For future agent",
    "",
    `${title} - vebees ${date}-nd Save to Inbox extension-eer hураав. Inbox-d triage huleej baina.`
  ];
  if (embeds.length) lines.push("", embeds.join("\n"));

  // --- Video / embed: IG/TikTok iframe, YouTube/Vimeo embed, шууд файл татах ---
  if (MEDIA.embedHtml) {
    lines.push("", "## 🎬 Video", "", MEDIA.embedHtml);
  } else if (MEDIA.videoPage) {
    lines.push("", "## 🎬 Video", "", `![](${MEDIA.videoPage})`);
  } else if (MEDIA.videoFile) {
    const dl = document.getElementById("dlVideo");
    let vdone = false;
    if (dl && dl.checked && apiKey) {
      try {
        const vext = ((MEDIA.videoFile.split("?")[0].match(/\.(mp4|webm|mov)$/i) || [])[1] || "mp4").toLowerCase();
        const vfn = `clip-${stamp}.${vext}`;
        const vr = await fetch(MEDIA.videoFile);
        if (vr.ok) {
          const vbuf = await vr.arrayBuffer();
          const vp = await fetch(`${endpoint}/vault/${encodeURI("_system/attachments/" + vfn)}`, {
            method: "PUT",
            headers: { "Authorization": "Bearer " + apiKey, "Content-Type": vext === "mov" ? "video/quicktime" : "video/" + vext },
            body: vbuf
          });
          if (vp.ok) { lines.push("", "## 🎬 Video", "", `![[${vfn}]]`); vdone = true; }
        }
      } catch (e) {}
    }
    if (!vdone) lines.push("", "## 🎬 Video", "", `![](${MEDIA.videoFile})`);
  } else if (MEDIA.ogVideo) {
    lines.push("", `> 🎬 Video: ${MEDIA.ogVideo}`);
  }

  if (sel) lines.push("", "## Temdeglesen heseg", "", sel);
  if (claudeTask) lines.push("", "## 🤖 Claude-d daalgavar", "", claudeTask);
  lines.push("", "## ✍️ Minii temdeglel", "", (note || ""));
  lines.push("", "## Eh survalj", "", `- ${url}`, "");
  const content = lines.join("\n");

  ok.textContent = "Хадгалж байна...";
  const INBOX = await inboxDir(apiKey, endpoint);

  // --- Ded 1: Local REST API (fokus solihgui) ---
  if (apiKey) {
    try {
      const r = await fetch(`${endpoint}/vault/${encodeURI(INBOX + "/" + base + ".md")}`, {
        method: "PUT",
        headers: { "Authorization": "Bearer " + apiKey, "Content-Type": "text/markdown" },
        body: content
      });
      if (r.ok) { ok.textContent = "✅ Inbox-д хадгаллаа (Obsidian нээгдээгүй)"; btn.disabled = false; return; }
      ok.textContent = `REST алдаа ${r.status} - Obsidian-аар оролдож байна...`;
    } catch (e) {
      ok.textContent = "REST холбогдсонгүй - Obsidian-аар оролдож байна...";
    }
  }

  // --- Ded 2: obsidian:// fallback (Obsidian urd garna) ---
  const VAULT = (await getCfg()).vault;
  if (!VAULT) { ok.textContent = "Options-д vault-ийн нэр (эсвэл ID) оруул."; btn.disabled = false; return; }
  const uri = `obsidian://new?vault=${encodeURIComponent(VAULT)}&file=${encodeURIComponent(INBOX + "/" + base)}&content=${encodeURIComponent(content)}`;
  window.location.href = uri;
  setTimeout(() => {
    ok.textContent = apiKey ? "Obsidian-аар хадгаллаа" : "Хадгаллаа. Фокус солихгүй болгохын тулд Options-д API key оруул.";
    btn.disabled = false;
  }, 400);
});
