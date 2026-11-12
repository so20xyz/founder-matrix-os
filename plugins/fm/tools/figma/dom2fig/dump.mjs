// node dump.mjs <slug> <selector> <out.json> [theme]
import { chromium } from 'playwright-core';
import fs from 'fs';
const [slug, sel, out, theme = 'light'] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
const p = await b.newPage({ viewport: { width: 1400, height: 2400 }, deviceScaleFactor: 1, colorScheme: theme, reducedMotion: 'reduce' });
await p.goto((process.env.BASE || "https://thinkstate.site/#/") + slug, { waitUntil: 'networkidle' });
await p.waitForSelector(sel, { timeout: 20000 });
await p.waitForTimeout(+(process.env.SETTLE || 5000)); // let animated/stateful components reach their end state
const tree = await p.$eval(sel, (root) => {
  const R = root.getBoundingClientRect();
  const px = v => parseFloat(v) || 0;
  // oklab()/color-mix()/color() → rgb via canvas so Figma's SVG parser understands it
  const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', { willReadFrequently: true });
  const normc = v => { if (!/oklab|oklch|color\(|color-mix|lab\(|lch\(/.test(v)) return v;
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = v; cx.fillRect(0, 0, 1, 1); const [r, g, b, a] = cx.getImageData(0, 0, 1, 1).data;
    return `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`; };
  function walk(el) {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || r.width === 0 && r.height === 0) return null;
    // visually-hidden (sr-only) text: 1px box, clip or clip-path inset
    if (r.width <= 1.5 && r.height <= 1.5 || /rect\(0/.test(cs.clip) || /inset\(50%/.test(cs.clipPath)) return null;
    const n = {
      tag: el.tagName.toLowerCase(), cls: (el.getAttribute('class') || '').toString().split(' ')[0],
      x: r.left - R.left, y: r.top - R.top, w: r.width, h: r.height,
      display: cs.display, dir: cs.flexDirection, gap: px(cs.columnGap), rowGap: px(cs.rowGap), wrap: cs.flexWrap,
      ai: cs.alignItems, jc: cs.justifyContent,
      pad: [px(cs.paddingTop), px(cs.paddingRight), px(cs.paddingBottom), px(cs.paddingLeft)],
      bg: normc(cs.backgroundColor), radius: [px(cs.borderTopLeftRadius), px(cs.borderTopRightRadius), px(cs.borderBottomRightRadius), px(cs.borderBottomLeftRadius)],
      bw: [px(cs.borderTopWidth), px(cs.borderRightWidth), px(cs.borderBottomWidth), px(cs.borderLeftWidth)], bc: normc([cs.borderTopColor, cs.borderRightColor, cs.borderBottomColor, cs.borderLeftColor][[px(cs.borderTopWidth), px(cs.borderRightWidth), px(cs.borderBottomWidth), px(cs.borderLeftWidth)].findIndex(v => v > 0)] || cs.borderTopColor), _: 0, bs: cs.borderTopStyle,
      shadow: cs.boxShadow, opacity: +cs.opacity, overflow: cs.overflow,
      ellipsis: cs.textOverflow === 'ellipsis', ws: cs.whiteSpace,
    };
    const tcol = (c) => { const s = getComputedStyle(c); return /rgba\(.*, 0\)$/.test(s.color) || s.webkitTextFillColor === 'transparent' || s.backgroundClip === 'text' ? 'rgb(113, 113, 122)' : normc(s.color); };
    if (el.tagName.toLowerCase() === 'svg') {
      const cl = el.cloneNode(true); const src = [el, ...el.querySelectorAll('*')], dst = [cl, ...cl.querySelectorAll('*')];
      src.forEach((s, i) => { const c = getComputedStyle(s), d = dst[i];
        for (const k of ['stop-color', 'stop-opacity', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'opacity', 'fill-opacity', 'stroke-opacity'])
          d.setAttribute(k, normc(c.getPropertyValue(k)).replace(/px/g, '').replace(/url\("(#[^"]+)"\)/, 'url($1)')); d.removeAttribute('class'); d.removeAttribute('style'); });
      cl.setAttribute('width', r.width); cl.setAttribute('height', r.height);
      n.svg = cl.outerHTML; return n; }
    if (['input', 'textarea', 'select'].includes(el.tagName.toLowerCase())) {
      const v = el.tagName === 'SELECT' ? (el.selectedOptions[0]?.text || '') : el.value; const ph = getComputedStyle(el, '::placeholder');
      n.text = v || el.placeholder || ''; n.input = true;
      n.font = { size: px(cs.fontSize), weight: cs.fontWeight, lh: cs.lineHeight, family: cs.fontFamily.split(',')[0].replace(/"/g, ''), color: v ? cs.color : ph.color, align: cs.textAlign, ls: px(cs.letterSpacing) };
      if (!n.text) delete n.text; return n; }
    const hasText = [...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim());
    const allInline = [...el.children].every(c => getComputedStyle(c).display.startsWith('inline') && c.tagName.toLowerCase() !== 'svg' && getComputedStyle(c).display !== 'inline-flex');
    const para = el.children.length && [...el.children].every(c => { const d = getComputedStyle(c).display; return d === 'inline' || d === 'inline-grid' || d === 'inline-block'; }) && !cs.display.includes('flex') && el.innerText.trim();
    if (para) {
      n.text = el.innerText.replace(/\s+/g, ' ');
      n.font = { size: px(cs.fontSize), weight: cs.fontWeight, lh: cs.lineHeight, family: cs.fontFamily.split(',')[0].replace(/"/g, ''), color: tcol(el), align: cs.textAlign, ls: px(cs.letterSpacing) };
      n.runs = [...el.childNodes].map(c => { const st = c.nodeType === 1 ? getComputedStyle(c) : cs; const t = (c.nodeType === 1 ? c.innerText : c.textContent).replace(/\s+/g, ' ');
        return { t, color: c.nodeType === 1 ? tcol(c) : tcol(el), weight: st.fontWeight, size: px(st.fontSize), bg: c.nodeType === 1 ? st.backgroundColor : null }; }).filter(r => r.t.length);
      return n;
    }
    if (hasText && allInline || (el.children.length === 0 && el.textContent.trim())) {
      n.text = el.innerText; n.font = { size: px(cs.fontSize), weight: cs.fontWeight, lh: cs.lineHeight, family: cs.fontFamily.split(',')[0].replace(/"/g, ''), color: tcol(el), align: cs.textAlign, ls: px(cs.letterSpacing) };
      return n;
    }
    n.children = [...el.children].map(walk).filter(Boolean);
    if (hasText) { // mixed: text node + flex children -> add text as child
      const t = [...el.childNodes].filter(c => c.nodeType === 3 && c.textContent.trim());
      for (const tn of t) { const rg = document.createRange(); rg.selectNode(tn); const rr = rg.getBoundingClientRect();
        n.children.push({ tag: '#text', x: rr.left - R.left, y: rr.top - R.top, w: rr.width, h: rr.height, text: tn.textContent.trim(),
          font: { size: px(cs.fontSize), weight: cs.fontWeight, lh: cs.lineHeight, family: cs.fontFamily.split(',')[0].replace(/"/g, ''), color: cs.color, align: 'left', ls: 0 } }); }
      n.children.sort((a, b) => a.x - b.x);
    }
    return n;
  }
  const t = walk(root);
  let a = root.parentElement, bg = 'rgba(0, 0, 0, 0)';
  while (a && /rgba\(.*, 0\)$/.test(getComputedStyle(a).backgroundColor)) a = a.parentElement;
  if (a) bg = getComputedStyle(a).backgroundColor;
  t.surface = bg; return t;
});
fs.writeFileSync(out, JSON.stringify(tree));
await p.screenshot({ path: out.replace('.json', '.png'), clip: await (await p.$(sel)).boundingBox() });
await b.close();
console.log('ok');
