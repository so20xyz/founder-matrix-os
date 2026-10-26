// @title Component audit — цонх зөвхөн instance-аас бүрдэж байгаа эсэх
// Хэрэглээ: __ROOTS__-г section id-уудын массиваар солиод  fig.py -d "<файл>" run -f component_audit.js
//   (жишээ: sed 's/__ROOTS__/["68:43114","68:68065"]/' component_audit.js > /tmp/x.js).
// Section → grid → цонх (grid-ийн шууд хүүхэд). Instance/component-ийн гадна байгаа TEXT ба дүрс
// (RECTANGLE, ELLIPSE, VECTOR, LINE…)-ийг «loose» гэж тоолно; layout frame тооцохгүй. Шинэ дэлгэц
// «бэлэн» гэхээс өмнө ажиллуул: loose ≈ 0 (зөвхөн workflow-ийн муруй холбоос үлдэж болно).
const ROOTS=__ROOTS__;
const UI=new Set(['TEXT','RECTANGLE','ELLIPSE','VECTOR','LINE','POLYGON','STAR']);
function inInstance(n,stop){let p=n.parent;while(p&&p!==stop){if(p.type==='INSTANCE'||p.type==='COMPONENT'||p.type==='COMPONENT_SET')return true;p=p.parent;}return false;}
const report=[];let total=0,totalInst=0;
for(const rid of ROOTS){const sec=await figma.getNodeByIdAsync(rid);if(!sec)continue;
  for(const grid of sec.children){if(!('children' in grid))continue;
    for(const w of grid.children){if(!('findAll' in w))continue;
      const titleTexts=new Set(w.children.filter(c=>c.type==='TEXT').map(c=>c.id));
      const loose=w.findAll(n=>UI.has(n.type)&&!titleTexts.has(n.id)&&!inInstance(n,w));
      const insts=w.findAll(n=>n.type==='INSTANCE'&&!inInstance(n,w)).length;
      const byType={};for(const n of loose)byType[n.type]=(byType[n.type]||0)+1;
      const sample=[...new Set(loose.filter(n=>n.type==='TEXT').map(n=>n.parent.name))].slice(0,6);
      report.push({id:w.id,name:w.name.slice(0,48),loose:loose.length,instances:insts,byType,parents:sample});total+=loose.length;totalInst+=insts;}}}
return {windows:report.length,loose:total,instances:totalInst,report:report.sort((a,b)=>b.loose-a.loose)};
