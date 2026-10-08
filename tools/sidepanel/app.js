const $=s=>document.querySelector(s);let D=null,view='today',tf='next-action',q='',calM=null,calMode='w',calStart=null,editing=null,mode='inbox',busy=false,pending=null;
const OPEN=['next-action','waiting','inbox'],STS=['next-action','waiting','inbox','someday','completed','cancelled'],PRI=['🔴','🟡','🟢'];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const days=d=>Math.round((new Date(d)-new Date(D.today))/864e5);
const pr=p=>({'🔴':0,high:0,'🟡':1,medium:1,'🟢':2,low:2}[p]??1);
const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const addD=(k,n)=>{const d=new Date(k+'T00:00');d.setDate(d.getDate()+n);return iso(d)};
const hue=s=>{let h=0;for(const c of s||'-')h=(h*31+c.charCodeAt(0))%360;return h};
const PAST=['var(--sage)','var(--peach)','var(--butter)','var(--lilac)','var(--sky)','var(--rose)'];const pcol=t=>t.project?PAST[hue(t.project)%PAST.length]:'var(--card2)';
function dueTag(d){if(!d)return'';const n=days(d);const c=n<0?'over':n<=2?'soon':'';const l=n<0?`${-n} хоног хоцорсон`:n==0?'өнөөдөр':n==1?'маргааш':d.slice(5);return `<span class="${c}">📅 ${l}</span>`}
function editor(t){const opt=(a,v)=>a.map(x=>`<option ${x===v?'selected':''}>${esc(x)}</option>`).join('');
  return `<div class="edit" data-ef="${esc(t.file)}"><label>status<select data-k="status">${opt(STS,t.status)}</select></label><label>priority<select data-k="priority"><option></option>${opt(PRI,t.priority)}</select></label>
  <label>due<input type="date" data-k="due" value="${esc((t.due||'').slice(0,10))}"></label><label>project<select data-k="project"><option></option>${opt(D.projects.map(p=>p.name),t.project)}</select></label>
  <label>owner<select data-k="owner"><option></option>${opt(['bd','claude'],t.owner)}</select></label></div>`}
function taskRow(t){return `<div class="card task" draggable="true" data-drag="${esc(t.file)}">${t.status!=='completed'?`<button class="chk" title="Дууссан" data-f="${esc(t.file)}"></button>`:''}<div class="t"><div class="n" data-open="${esc(t.file)}" style="cursor:pointer">${esc(t.priority)} ${esc(t.title)}</div><div class="meta">${dueTag(t.due)}${t.project?`<span>◆ ${esc(t.project)}</span>`:''}${t.status!=='next-action'?`<span class="pill">${esc(t.status)}</span>`:''}</div>${editing===t.file?editor(t):''}</div></div>`}
const sortT=a=>a.sort((x,y)=>(x.due?0:1)-(y.due?0:1)||(x.due||'').localeCompare(y.due||'')||pr(x.priority)-pr(y.priority));
function toast(m){const e=$('#toast');e.textContent=m;e.classList.add('on');setTimeout(()=>e.classList.remove('on'),1800)}
async function setProp(file,key,value){const r=await fetch('/api/prop',{method:'POST',body:JSON.stringify({file,key,value})});toast(r.ok?`✓ ${key} → ${value||'—'}`:'Алдаа');await load()}

function vToday(){
  const open=D.tasks.filter(t=>OPEN.includes(t.status));
  const over=sortT(open.filter(t=>t.due&&days(t.due)<0)), week=sortT(open.filter(t=>t.due&&days(t.due)>=0&&days(t.due)<=7));
  const act=D.projects.filter(p=>p.status==='active');
  const mt=D.meetings.filter(m=>m.date&&days(m.date)>=0&&days(m.date)<=7).sort((a,b)=>a.date.localeCompare(b.date));
  const fx=over[0]||week[0];
  return `<div class="bento">${fx?`<div class="focus span2"><div class="k">Одоо хамгийн чухал</div><div class="ti" data-open="${esc(fx.file)}">${esc(fx.title)}</div><div class="meta">${dueTag(fx.due)}${fx.project?`<span>◆ ${esc(fx.project)}</span>`:''}</div><button data-f="${esc(fx.file)}" class="chk2">Дууссан ✓</button></div>`:''}
  <div class="stat r"><span>хоцорсон</span><b>${over.length}</b></div><div class="stat a"><span>7 хоногт</span><b>${week.length}</b></div><div class="stat s"><span>next action</span><b>${open.filter(t=>t.status==='next-action').length}</b></div><div class="stat l"><span>хүлээж буй</span><b>${open.filter(t=>t.status==='waiting').length}</b></div></div>
  <h2>Идэвхтэй төсөл <small>${act.length}</small></h2>${act.map(p=>`<div class="card" data-dropproj="${esc(p.name)}"><b>${esc(p.icon)} ${esc(p.name)}</b><div class="meta">${p.open} нээлттэй · ${p.done} дууссан${p.due?' · '+dueTag(p.due):''}</div></div>`).join('')||'<p class="empty">—</p>'}
  ${over.length?`<h2>Хоцорсон <small>${over.length}</small></h2>${over.slice(0,8).map(taskRow).join('')}`:''}
  <h2>Энэ 7 хоног <small>${week.length}</small></h2>${week.map(taskRow).join('')||'<p class="empty">Хугацаатай таск алга</p>'}
  ${mt.length?`<h2>Уулзалт</h2>${mt.map(m=>`<div class="card"><b>${esc(m.title)}</b><div class="meta">${dueTag(m.date)}</div></div>`).join('')}`:''}
  <h2>Өнөөдрийн лог <small>${D.log.length}</small></h2><div class="log">${D.log.slice().reverse().map(l=>`<div><em>${l.time}</em><b>${esc(l.kind)}</b>${esc(l.text)}</div>`).join('')||'<p class="empty">Өнөөдөр бичлэг алга</p>'}</div>`}

function vTasks(){
  const st=['next-action','waiting','inbox','someday','completed'];
  const cnt=s=>D.tasks.filter(t=>t.status===s).length;
  let list=D.tasks.filter(t=>t.status===tf&&(!q||(t.title+t.project).toLowerCase().includes(q)));
  list=tf==='completed'?list.sort((a,b)=>(b.updated||'').localeCompare(a.updated||'')).slice(0,40):sortT(list);
  return `<div class="filters">${st.map(s=>`<button data-tf="${s}" data-dropst="${s}" class="${s===tf?'on':''}">${s} ${cnt(s)}</button>`).join('')}</div>
  <p class="meta" style="margin:-4px 0 8px">Таскийг дээрх товч руу чирвэл status солигдоно · нэр дээр дарвал засна</p>
  <input type="search" id="q" placeholder="Хайх…" value="${esc(q)}">${list.map(taskRow).join('')||'<p class="empty">Хоосон</p>'}`}

function vProjects(){
  const ord={active:0,planning:1,paused:2,someday:3,completed:4,archived:5};
  const ps=D.projects.slice().sort((a,b)=>(ord[a.status]??3)-(ord[b.status]??3));
  let cur='';return ps.map(p=>{let h='';if(p.status!==cur){cur=p.status;h=`<h2>${esc(cur||'—')} <small>${ps.filter(x=>x.status===cur).length}</small></h2>`}
    const tot=p.open+p.done;return h+`<div class="card proj" data-dropproj="${esc(p.name)}"><div class="hd"><b>${esc(p.icon)} ${esc(p.name)}</b><span class="meta">${p.open}/${tot}</span></div>${p.goal?`<div class="g">${esc(p.goal)}</div>`:''}${tot?`<div class="bar"><i style="width:${Math.round(p.done/tot*100)}%"></i></div>`:''}${p.next?`<div class="nx">▶️ ${esc(p.next)}</div>`:''}</div>`}).join('')}

function evs(k,byT,byM){return (byM[k]||[]).map(x=>`<div class="ev m">🗓 ${esc(x.title)}</div>`).join('')+(byT[k]||[]).map(x=>`<div class="ev ${x.status==='completed'?'done':''}" draggable="true" data-drag="${esc(x.file)}" data-open="${esc(x.file)}" style="background:${pcol(x)}">${esc(x.priority)} ${esc(x.title)}</div>`).join('')}
function vCal(){
  calStart=calStart||D.today;const t=new Date(D.today);calM=calM||new Date(t.getFullYear(),t.getMonth(),1);
  const byT={},byM={};D.tasks.forEach(x=>{if(x.due&&x.status!=='cancelled')(byT[x.due.slice(0,10)]??=[]).push(x)});D.meetings.forEach(x=>{if(x.date)(byM[x.date.slice(0,10)]??=[]).push(x)});(D.social||[]).forEach(x=>{if(x.publish_date)(byM[x.publish_date.slice(0,10)]??=[]).push({title:'📣 '+x.title})});
  const seg=`<div class="seg">${[['w','7 хоног'],['3','3 хоног'],['m','Сар']].map(([k,l])=>`<button data-calmode="${k}" class="${calMode===k?'on':''}">${l}</button>`).join('')}</div>`;
  let body;
  if(calMode==='m'){const y=calM.getFullYear(),m=calM.getMonth(),start=new Date(y,m,1-((new Date(y,m,1).getDay()+6)%7));let cells='';
    for(let i=0;i<42;i++){const d=new Date(start);d.setDate(start.getDate()+i);const k=iso(d);cells+=`<div class="d ${d.getMonth()!==m?'x':''} ${k===D.today?'today':''}" data-d="${k}" data-dropday="${k}">${d.getDate()}${evs(k,byT,byM)}</div>`}
    body=`<div class="calnav"><button data-cm="-1">‹</button><b>${y} · ${m+1}-р сар</b><button data-cm="1">›</button></div><div class="cal mon">${['Да','Мя','Лх','Пү','Ба','Бя','Ня'].map(x=>`<div class="dh">${x}</div>`).join('')}${cells}</div>`}
  else if(calMode==='w'){const wd=['Ням','Даваа','Мягмар','Лхагва','Пүрэв','Баасан','Бямба'],ks=[...Array(7)].map((_,i)=>addD(calStart,i));
    body=`<div class="calnav"><button data-cs="-7">‹</button><button data-cs="0" style="font-size:12px">Өнөөдөр</button><button data-cs="7">›</button></div><div class="stack">${ks.map(k=>{const n=(byT[k]||[]).length+(byM[k]||[]).length;return `<div class="dy ${k===D.today?'today':''} ${n?'has':''}" data-dropday="${k}"><div class="dn">${wd[new Date(k+'T00:00').getDay()]}<small>${k.slice(5).replace('-','.')}${n?' · '+n:''}</small></div>${n?`<div class="evs">${evs(k,byT,byM)}</div>`:''}</div>`}).join('')}</div>`}
  else{const n=+calMode,ks=[...Array(n)].map((_,i)=>addD(calStart,i)),wd=['Ня','Да','Мя','Лх','Пү','Ба','Бя'];
    body=`<div class="calnav"><button data-cs="-${n}">‹</button><button data-cs="0" style="font-size:12px">Өнөөдөр</button><button data-cs="${n}">›</button></div>
    <div class="days" style="grid-template-columns:repeat(${n},1fr)">${ks.map(k=>`<div class="col ${k===D.today?'today':''}" data-dropday="${k}"><div class="ch">${wd[new Date(k+'T00:00').getDay()]}<b>${+k.slice(8)}</b></div>${evs(k,byT,byM)}</div>`).join('')}</div>`}
  const tray=sortT(D.tasks.filter(x=>x.status==='next-action'&&!x.due));
  const ed=editing&&D.tasks.find(x=>x.file===editing);
  return seg+body+(ed?`<h2>Засах</h2>${taskRow(ed)}`:'')+
    `<h2>Хугацаагүй <small>${tray.length} · өдөр рүү чир</small></h2><div class="tray">${tray.map(x=>`<div class="ev" draggable="true" data-drag="${esc(x.file)}" data-open="${esc(x.file)}" style="background:${pcol(x)}">${esc(x.title)}</div>`).join('')}</div>`}

const SST=['idea','draft','ready','scheduled','published'],SIC={idea:'💡',draft:'✏️',ready:'✅',scheduled:'⏰',published:'📣',archived:'🗄'};
const SLOT={2:'carousel',5:'carousel',0:'reel'};let socStart=null;
function socCard(p,big){return `<div class="card soc" draggable="true" data-drag="${esc(p.file)}">${p.thumb?`<img src="${encodeURI(p.thumb)}" loading="lazy">`:'<div class="ph">'+(SIC[p.status]||'')+'</div>'}<div class="t"><div class="n">${esc(p.title)}</div><div class="meta"><span class="pill">${SIC[p.status]||''} ${esc(p.status)}</span><span>${esc(p.format)}</span>${p.publish_date?dueTag(p.publish_date):'<span>огноогүй</span>'}${p.url?`<a href="${esc(p.url)}" target="_blank">↗</a>`:''}</div>${big&&p.summary?`<p class="meta">${esc(p.summary)}</p>`:''}</div></div>`}
function vSocial(){const S=D.social||[];socStart=socStart||(()=>{const d=new Date(D.today+'T00:00');d.setDate(d.getDate()-((d.getDay()+6)%7));return iso(d)})();
  const by={};S.forEach(p=>{if(p.publish_date)(by[p.publish_date.slice(0,10)]??=[]).push(p)});
  const ks=[...Array(28)].map((_,i)=>addD(socStart,i));
  const cells=ks.map(k=>{const dw=new Date(k+'T00:00').getDay(),ps=by[k]||[];return `<div class="d ${k===D.today?'today':''} ${k<D.today?'x':''}" data-dropday="${k}">${+k.slice(8)}${ps.map(p=>`<div class="ev" draggable="true" data-drag="${esc(p.file)}" style="background:${p.status==='published'?'var(--sage)':p.status==='ready'||p.status==='scheduled'?'var(--sky)':'var(--butter)'}">${SIC[p.status]||''} ${esc(p.title.slice(0,22))}</div>`).join('')}${!ps.length&&SLOT[dw]&&k>=D.today?`<div class="slot">+ ${SLOT[dw]}</div>`:''}</div>`}).join('');
  const cnt=s=>S.filter(p=>p.status===s).length,tray=S.filter(p=>!p.publish_date&&p.status!=='archived');
  const wk=S.filter(p=>p.publish_date&&days(p.publish_date)>=0&&days(p.publish_date)<7).length;
  return `<div class="bento"><div class="stat s"><span>7 хоногт</span><b>${wk}/3</b></div><div class="stat a"><span>бэлэн</span><b>${cnt('ready')+cnt('scheduled')}</b></div><div class="stat l"><span>санаа</span><b>${cnt('idea')+cnt('draft')}</b></div><div class="stat r"><span>нийтэлсэн</span><b>${cnt('published')}</b></div></div>
  <div class="filters">${SST.map(s=>`<button data-dropst="${s}">${SIC[s]} ${s} ${cnt(s)}</button>`).join('')}</div>
  <p class="meta" style="margin:-4px 0 8px">Хэмнэл: Мя · Ба carousel, Ня reel · постыг өдөр рүү чирвэл огноо, дээрх товч руу чирвэл status солигдоно</p>
  <div class="calnav"><button data-ss="-7">‹</button><button data-ss="0" style="font-size:12px">Энэ 7 хоног</button><button data-ss="7">›</button></div>
  <div class="cal mon">${['Да','Мя','Лх','Пү','Ба','Бя','Ня'].map(x=>`<div class="dh">${x}</div>`).join('')}${cells}</div>
  <h2>Товлоогүй <small>${tray.length} · өдөр рүү чир</small></h2>${tray.map(p=>socCard(p,1)).join('')||'<p class="empty">—</p>'}
  <h2>Бүх пост <small>${S.length}</small></h2>${S.slice().sort((a,b)=>(b.publish_date||'9').localeCompare(a.publish_date||'9')).map(p=>socCard(p)).join('')}
  <p class="meta">Сан: 08-Studio/Social Posts · эзэн: 07 Social Admin</p>`}

function vResearch(){return `<h2>Сүүлийн судалгаа, тэмдэглэл</h2>`+D.research.map(r=>`<div class="card res"><div class="n">${esc(r.title)}</div><div class="meta"><span class="pill">${esc(r.type)}</span><span>${esc(r.when)}</span></div>${r.summary?`<p>${esc(r.summary)}</p>`:''}</div>`).join('')}
function vChat(){const h=(D.chat||[]).concat(pending?[{who:'bd',text:pending,t:'одоо'}]:[]);
  return `<div class="seg"><button data-newchat="1">+ Шинэ яриа</button></div><div class="chat">${h.map(m=>`<div class="msg ${m.who}">${esc(m.text)}<small>${esc(m.t)}</small></div>`).join('')||'<p class="empty">Доор бичээд Enter — Claude vault-аа уншиж хариулна, шаардвал тэмдэглэл засна.</p>'}${busy?'<div class="typing">Claude ажиллаж байна…</div>':''}</div>`}

function setMode(m){mode=m;$('#mode').textContent=m==='claude'?'Claude':'Inbox';$('#capin').placeholder=m==='claude'?'Claude-д бичих…':'Санаа, таск → 02-GTD/inbox'}
function render(){if(!D)return;$('#main').innerHTML={today:vToday,tasks:vTasks,projects:vProjects,cal:vCal,social:vSocial,research:vResearch,chat:vChat}[view]();
  if(view==='chat')scrollTo(0,document.body.scrollHeight);
  const qi=$('#q');if(qi){qi.oninput=e=>{q=e.target.value.toLowerCase();const p=qi.selectionStart;render();const n=$('#q');n.focus();n.setSelectionRange(p,p)}}}
async function load(){try{D=await (await fetch('/api/data')).json();const d=new Date(D.today);$('#date').innerHTML=`<small>${D.today.slice(5).replace('-','.')} · ${D.tasks.filter(t=>OPEN.includes(t.status)).length} нээлттэй</small>${['Ням','Даваа','Мягмар','Лхагва','Пүрэв','Баасан','Бямба'][d.getDay()]}`;render()}catch(e){$('#main').innerHTML='<p class="empty">Сервер ажиллахгүй байна — python _system/tools/sidepanel/server.py</p>'}}

$('#tabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;view=b.dataset.v;editing=null;document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===b));setMode(view==='chat'?'claude':mode);render();scrollTo(0,0)};
$('#mode').onclick=()=>setMode(mode==='claude'?'inbox':'claude');
$('#main').onclick=async e=>{const c=e.target.closest('.chk,.chk2');
  if(c){c.disabled=true;await setProp(c.dataset.f,'status','completed');return}
  if(e.target.closest('.edit'))return;
  const o=e.target.closest('[data-open]');if(o){editing=editing===o.dataset.open?null:o.dataset.open;render();return}
  const f=e.target.closest('[data-tf]');if(f){tf=f.dataset.tf;render();return}
  const cm=e.target.closest('[data-cm]');if(cm){calM=new Date(calM.getFullYear(),calM.getMonth()+ +cm.dataset.cm,1);render();return}
  const cs=e.target.closest('[data-cs]');if(cs){calStart=+cs.dataset.cs?addD(calStart,+cs.dataset.cs):D.today;render();return}
  const ss=e.target.closest('[data-ss]');if(ss){socStart=+ss.dataset.ss?addD(socStart,+ss.dataset.ss):null;render();return}
  const md=e.target.closest('[data-calmode]');if(md){calMode=md.dataset.calmode;render();return}
  const d=e.target.closest('[data-d]');if(d){calStart=d.dataset.d;calMode='1';render();return}
  if(e.target.closest('[data-newchat]')){await ask('',true);return}
  const p=e.target.closest('.proj');if(p)p.classList.toggle('open')};
$('#main').onchange=e=>{const i=e.target.closest('[data-k]');if(i)setProp(i.closest('[data-ef]').dataset.ef,i.dataset.k,i.value)};

// drag & drop: таск → өдөр (due), status товч (status), төсөл (project)
let dragF=null;
$('#main').addEventListener('dragstart',e=>{const t=e.target.closest('[data-drag]');if(!t)return;dragF=t.dataset.drag;t.classList.add('dragging');e.dataTransfer.setData('text/plain',dragF)});
$('#main').addEventListener('dragend',()=>document.querySelectorAll('.dragging,.drop').forEach(x=>x.classList.remove('dragging','drop')));
const tgt=e=>e.target.closest('[data-dropday],[data-dropst],[data-dropproj]');
$('#main').addEventListener('dragover',e=>{const t=tgt(e);if(t&&dragF){e.preventDefault();document.querySelectorAll('.drop').forEach(x=>x!==t&&x.classList.remove('drop'));t.classList.add('drop')}});
$('#main').addEventListener('drop',e=>{const t=tgt(e);if(!t||!dragF)return;e.preventDefault();const f=dragF;dragF=null;
  if(t.dataset.dropday)setProp(f,f.includes('/Social Posts/')?'publish_date':'due',t.dataset.dropday);else if(t.dataset.dropst)setProp(f,'status',t.dataset.dropst);else setProp(f,'project',t.dataset.dropproj)});

async function ask(text,fresh=false){if(fresh&&!confirm('Шинэ яриа эхлүүлэх үү?'))return;busy=true;pending=text||null;render();
  try{const r=await fetch('/api/ask',{method:'POST',body:JSON.stringify({text:text||'Шинэ яриа. Өнөөдрийн хамгийн чухал 3 зүйлийг товч хэл.',new:fresh})});if(!r.ok)toast((await r.json()).error||'Алдаа')}catch(e){toast('Алдаа')}
  busy=false;pending=null;await load()}
$('#cap').onsubmit=async e=>{e.preventDefault();const v=$('#capin').value.trim();if(!v||busy)return;$('#capin').value='';
  if(mode==='claude'){if(view!=='chat')document.querySelector('[data-v=chat]').click();await ask(v);return}
  const r=await fetch('/api/capture',{method:'POST',body:JSON.stringify({text:v})});toast(r.ok?'→ 02-GTD/inbox':'Алдаа')};
try{const th=localStorage.getItem('inai-theme');if(th)document.documentElement.dataset.theme=th}catch(e){}
$('#theme').onclick=()=>{const r=document.documentElement;r.dataset.theme=r.dataset.theme==='light'?'dark':'light';try{localStorage.setItem('inai-theme',r.dataset.theme)}catch(e){}};
load();setInterval(()=>{if(document.visibilityState==='visible'&&!busy&&!editing&&!document.activeElement.matches('input,select'))load()},60000);
