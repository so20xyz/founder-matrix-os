const zlib=require('zlib'),fs=require('fs');module.exports=(rects,file,R=40)=>{const W=1080,H=1920;const raw=Buffer.alloc((W*4+1)*H);
// дотор нь бүтэн багтсан тэгш өнцөгт (PiP камер) = хөвөгч карт: эргэн тойронд G px зай гаргаж, булангуудыг нь бөөрөнхийлнө
const al=(x,y,X,Y,RW,RH,r)=>{if(x<X||x>=X+RW||y<Y||y>=Y+RH)return 0;if(!r)return 255;const cx=Math.min(Math.max(x,X+r),X+RW-r-1),cy=Math.min(Math.max(y,Y+r),Y+RH-r-1);const d=Math.hypot(x-cx,y-cy);return d<=r-0.5?255:d>=r+0.5?0:Math.round(255*(r+0.5-d))};
const G=0,inside=(a,b)=>a!==b&&a[0]>=b[0]&&a[1]>=b[1]&&a[0]+a[2]<=b[0]+b[2]&&a[1]+a[3]<=b[1]+b[3];
const fl=rects.filter(a=>rects.some(b=>inside(a,b))),base=rects.filter(a=>!fl.includes(a));
for(let y=0;y<H;y++){raw[y*(W*4+1)]=0;for(let x=0;x<W;x++){let a=0;for(const [X,Y,RW,RH] of base)a=Math.max(a,al(x,y,X,Y,RW,RH,R));
for(const [X,Y,RW,RH] of fl){const o=al(x,y,X-G,Y-G,RW+2*G,RH+2*G,G?R+G:0);if(o)a=Math.max(al(x,y,X,Y,RW,RH,R),Math.round(a*(255-o)/255))}
const o=y*(W*4+1)+1+x*4;raw[o]=raw[o+1]=raw[o+2]=255;raw[o+3]=a}}
const crc=b=>{let c,t=[];for(let n=0;n<256;n++){c=n;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;t[n]=c>>>0}c=0xffffffff;for(const x of b)c=t[(c^x)&255]^(c>>>8);return (c^0xffffffff)>>>0};
const ch=(ty,d)=>{const l=Buffer.alloc(4);l.writeUInt32BE(d.length);const td=Buffer.concat([Buffer.from(ty),d]);const c=Buffer.alloc(4);c.writeUInt32BE(crc(td));return Buffer.concat([l,td,c])};
const ih=Buffer.alloc(13);ih.writeUInt32BE(W,0);ih.writeUInt32BE(H,4);ih[8]=8;ih[9]=6;fs.writeFileSync(file,Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),ch('IHDR',ih),ch('IDAT',zlib.deflateSync(raw)),ch('IEND',Buffer.alloc(0))]))}
