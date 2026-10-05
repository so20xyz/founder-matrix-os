// @title Contrast check (WCAG 2.2)
// Хэрэглээ: fig.py run -f contrast_check.js (ROOT_ID-г орлуулна). Frame бүрийн TEXT ба сум (VECTOR)-ын өнгийг
// доор нь байгаа хамгийн дээд цул өнгөт давхаргатай харьцуулна. IG дээр 1080px зураг ~360pt болж харагддаг тул
// «том текст» = ≥ 48px (bold ≥ 40px) → 3:1, бусад текст → 4.5:1, сум/дүрс → 3:1. Зураг/градиент дээрх бол «гараар шалга».
const ROOT=await figma.getNodeByIdAsync(__ROOT__);
const lum=c=>{const f=x=>x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4);return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b)};
const ratio=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)};
const solid=n=>{const f=(n.fills&&n.fills!==figma.mixed)?n.fills.filter(p=>p.visible!==false):[];const s=f.find(p=>p.type==='SOLID');return s?{c:s.color,o:(s.opacity??1)*(n.opacity??1)}:null};
const hasImg=n=>n.fills&&n.fills!==figma.mixed&&n.fills.some(p=>p.visible!==false&&(p.type==='IMAGE'||p.type.startsWith('GRADIENT')));
const box=n=>n.absoluteBoundingBox;const inside=(p,b)=>b&&p.x>=b.x&&p.x<=b.x+b.width&&p.y>=b.y&&p.y<=b.y+b.height;
const blend=(top,o,bot)=>({r:top.r*o+bot.r*(1-o),g:top.g*o+bot.g*(1-o),b:top.b*o+bot.b*(1-o)});
// Доорх давхаргын өнгө: frame дотор painter's order-оор ард байгаа, цэгийг агуулсан бүх давхаргаас
function bgAt(frame,node,pt){const all=frame.findAll(()=>true);const idx=all.indexOf(node);let color=solid(frame)?.c||{r:1,g:1,b:1};let img=false;
 let anc=node.parent,base=null;while(anc&&anc!==frame){const s=solid(anc);if(s&&s.o>0.5){base=s.c;break}anc=anc.parent}
 const below=all.slice(0,idx).filter(n=>n.visible&&!(node.type==='TEXT'&&n.type==='TEXT')&&!n.name.startsWith('texture')&&inside(pt,box(n))&&!isAncestor(n,node));
 for(const n of below){if(n.type==='TEXT'||n.type==='VECTOR')continue;if(hasImg(n)){img=true;color=null;continue;}const s=solid(n);if(s){color=color?blend(s.c,s.o,color):s.c;img=img&&s.o<1;}}
 if(base&&!img)color=base;return {color,img}}
function isAncestor(a,n){let p=n.parent;while(p){if(p===a)return true;p=p.parent}return false}
const hex=c=>'#'+[c.r,c.g,c.b].map(x=>Math.round(x*255).toString(16).padStart(2,'0')).join('').toUpperCase();
const out=[];const kids=(ROOT.children||[]).filter(c=>c.type==='FRAME');const numbered=kids.filter(c=>/^\d\d · /.test(c.name));
const frames=ROOT.type==='FRAME'?[ROOT]:(numbered.length?numbered:kids);
for(const fr of frames){for(const n of fr.findAll(x=>(x.type==='TEXT'||(x.type==='VECTOR'&&x.strokes&&x.strokes.length))&&x.visible)){
 const b=box(n);if(!b)continue;const pt={x:b.x+b.width/2,y:b.y+b.height/2};
 const fg=n.type==='TEXT'?solid(n):(n.strokes[0].type==='SOLID'?{c:n.strokes[0].color,o:n.strokes[0].opacity??1}:null);if(!fg)continue;
 const {color,img}=bgAt(fr,n,pt);const label=n.type==='TEXT'?n.characters.replace(/\n/g,' ').slice(0,34):'сум / дүрс';
 if(img||!color){out.push({f:fr.name.slice(0,14),t:label,res:'ЗУРАГ дээр — гараар'});continue;}
 const fgc=fg.o<1?blend(fg.c,fg.o,color):fg.c;const r=ratio(fgc,color);
 let need=3;if(n.type==='TEXT'){const sz=n.fontSize===figma.mixed?40:n.fontSize;const st=n.fontName===figma.mixed?'':n.fontName.style;need=(sz>=48||(sz>=40&&/Bold|Black|SemiBold/.test(st)))?3:4.5;}
 if(r<need+0.0001||r<4.5)out.push({f:fr.name.slice(0,14),t:label,fg:hex(fgc),bg:hex(color),r:+r.toFixed(2),need,res:r>=need?'OK (хилийн)':'FAIL'});}}
const fails=out.filter(o=>o.res==='FAIL');return {checked:frames.length,fail:fails.length,manual:out.filter(o=>o.res.startsWith('ЗУРАГ')).length,items:out};
