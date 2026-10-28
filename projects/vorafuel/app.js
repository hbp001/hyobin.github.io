'use strict';
const $=s=>document.querySelector(s), canvas=$('#scene'),ctx=canvas.getContext('2d');
let DATA,chosen=0,progress=0,playing=false,last=0,lang=new URLSearchParams(location.search).get('lang')==='ko'?'ko':'en';
const C={bg:'#071820',panel:'#0c242e',grid:'#203d48',ink:'#eef8f7',muted:'#8cabb7',mint:'#63efc4',gold:'#e6b97b',purple:'#baabf0',past:'#a3b5c1'};
const tr=(en,ko)=>lang==='ko'?ko:en;
function text(s,x,y,size=18,color=C.ink,weight=400){ctx.fillStyle=color;ctx.font=`${weight} ${size}px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif`;ctx.fillText(s,x,y);}
function line(points,color,width=2,dash=[]){ctx.beginPath();let open=false;for(const p of points){if(!p||!Number.isFinite(p[0])||!Number.isFinite(p[1])){open=false;continue;}if(!open){ctx.moveTo(...p);open=true;}else ctx.lineTo(...p);}ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.stroke();ctx.setLineDash([]);}
function panel(x,y,w,h){ctx.fillStyle=C.panel;ctx.beginPath();ctx.roundRect(x,y,w,h,16);ctx.fill();ctx.strokeStyle=C.grid;ctx.lineWidth=1;ctx.stroke();}
const finite=x=>typeof x==='number'&&Number.isFinite(x);
function metrics(c){const mae=a=>a.reduce((s,v,i)=>s+Math.abs(v-c.gt[i]),0)/12;const e=mae(c.predictions.Ours);return {mae:e,rf:100*(1-e/mae(c.predictions.RF)),chrono:100*(1-e/mae(c.predictions['Chronos-2']))};}
function route(c,t){const x=40,y=144,w=548,h=478;panel(x,y,w,h);text(tr('OBSERVED VESSEL TRACK','실측 선박 항적'),x+24,y+35,16,C.muted,600);text(tr('Transformed coordinates · schematic view','변환 좌표 · 개략 항적도'),x+24,y+61,14,C.muted);
 ctx.save();ctx.beginPath();ctx.rect(x+20,y+80,w-40,h-110);ctx.clip();
 for(let i=0;i<12;i++){line([[x+i*52,y+80],[x+i*52,y+h]],C.grid,.6);line([[x,y+95+i*38],[x+w,y+95+i*38]],C.grid,.6);}
 const points=c.route.filter(p=>finite(p.x)&&finite(p.y));let xmin=Math.min(...points.map(p=>p.x)),xmax=Math.max(...points.map(p=>p.x)),ymin=Math.min(...points.map(p=>p.y)),ymax=Math.max(...points.map(p=>p.y));
 let scale=Math.min((w-115)/Math.max(.1,xmax-xmin),(h-175)/Math.max(.1,ymax-ymin));const X=v=>x+w/2+(v-(xmin+xmax)/2)*scale,Y=v=>y+95+(h-125)/2-(v-(ymin+ymax)/2)*scale;
 const visible=c.route.map(p=>finite(p.x)&&finite(p.y)&&p.hour<=t?[X(p.x),Y(p.y)]:null);
 line(c.route.map(p=>finite(p.x)&&finite(p.y)?[X(p.x),Y(p.y)]:null),'#294b58',2,[5,7]);
 ctx.shadowColor=C.mint;ctx.shadowBlur=18;line(visible,C.mint,3.5);ctx.shadowBlur=0;
 const current=c.route.filter(p=>p.hour<=t).at(-1);
 if(current&&finite(current.x)&&finite(current.y)){
  const i=c.route.indexOf(current);const before=c.route.slice(0,i).reverse().find(p=>finite(p.x)&&finite(p.y));
  const angle=before?Math.atan2(Y(current.y)-Y(before.y),X(current.x)-X(before.x))+Math.PI/2:0;
  ctx.save();ctx.translate(X(current.x),Y(current.y));ctx.strokeStyle='#63efc455';ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(0,0,23+Math.sin(progress*35)*4,0,Math.PI*2);ctx.stroke();ctx.rotate(angle);ctx.shadowColor=C.mint;ctx.shadowBlur=20;ctx.fillStyle=C.ink;ctx.beginPath();ctx.moveTo(0,-17);ctx.lineTo(10,13);ctx.lineTo(0,8);ctx.lineTo(-10,13);ctx.closePath();ctx.fill();ctx.restore();
 }
 ctx.restore();text('N',x+w-43,y+40,13,C.muted,600);line([[x+w-38,y+49],[x+w-38,y+70]],C.muted,1);text(tr('TRACK REPLAY  /  not a predicted route','항적 재생  /  예측 항로 아님'),x+24,y+h-21,13,C.muted);
}
function chart(c,t){const x=614,y=144,w=946,h=478;panel(x,y,w,h);text(tr('PAST INPUT → FUTURE FUEL FORECAST','과거 입력 → 미래 연료 소비 예측'),x+28,y+35,19,C.ink,600);text(tr('One forecast · normalized fuel per 30-minute bin','단일 예측 · 30분 구간별 정규화 연료 소비량'),x+28,y+62,14,C.muted);
 const left=x+62,right=x+w-28,top=y+113,bottom=y+h-73;const X=h=>left+(h+6.5)/12.5*(right-left);
 const history=[];for(let i=2;i<36;i+=3){const vals=c.fuel.slice(i-2,i+1);history.push({hour:-6.3333333333+i/6,v:vals.every(finite)?vals.reduce((a,b)=>a+b,0):null});}
 const max=Math.max(...c.gt,...Object.values(c.predictions).flat(),...history.map(p=>p.v||0))*1.15;const Y=v=>bottom-v/max*(bottom-top);
 ctx.fillStyle='#ffffff05';ctx.fillRect(left,top,X(0)-left,bottom-top);ctx.fillStyle='#63efc407';ctx.fillRect(X(0),top,right-X(0),bottom-top);
 for(let i=0;i<5;i++){const v=max*i/4;line([[left,Y(v)],[right,Y(v)]],C.grid,1);text(v.toFixed(2),left-47,Y(v)+5,12,C.muted);}
 for(const h of [-6,-4,-2,0,2,4,6]){line([[X(h),top],[X(h),bottom]],C.grid,.6);text((h>0?'+':'')+h+' h',X(h)-12,bottom+27,13,C.muted);}
 text(tr('HISTORY','과거 입력'),left+10,top-15,13,C.muted,600);text(tr('FORECAST','미래 예측'),X(0)+15,top-15,13,C.mint,600);
 line([[X(0),top-5],[X(0),bottom]],'#87a6af',1.5,[5,5]);
 line(history.map(p=>p.v===null?null:[X(p.hour),Y(p.v)]),C.past,3);
 for(const [name,color] of [['Chronos-2',C.purple],['RF',C.gold],['Ours',C.mint]]){const p=c.predictions[name];ctx.globalAlpha=name==='Ours'?1:.65;line(p.map((v,i)=>[X((i+1)/2),Y(v)]),color,name==='Ours'?4:2,name==='Ours'?[]:[7,5]);}ctx.globalAlpha=1;
 const gt=c.gt.map((v,i)=>(i+1)/2<=t?[X((i+1)/2),Y(v)]:null);line(gt,C.ink,2.5);for(const p of gt)if(p){ctx.fillStyle=C.ink;ctx.beginPath();ctx.arc(...p,3.4,0,2*Math.PI);ctx.fill();}
 const cursor=X(t);line([[cursor,top],[cursor,bottom]],'#eef8f755',1);ctx.fillStyle='#eef8f7';ctx.beginPath();ctx.arc(cursor,top-4,3,0,7);ctx.fill();
 const legends=[['VORAFuel',C.mint],[tr('Observed GT','실측 정답'),C.ink],['Random Forest',C.gold],['Chronos-2',C.purple]];legends.forEach(([s,col],i)=>{line([[x+30+i*215,y+h-22],[x+50+i*215,y+h-22]],col,3);text(s,x+59+i*215,y+h-17,13,C.muted);});
}
function inputs(c){const names=[['SOG','Speed','속도'],['mean_rpm','Engine RPM','기관 RPM'],['mean_pitch','Propeller pitch','프로펠러 피치'],['kma_fc_wave_m','Wave height','파고']];
 for(let i=0;i<4;i++){let x=40+i*385,y=648,w=365,h=153;panel(x,y,w,h);const ch=c.input_channels.find(v=>v.name===names[i][0]);text(tr(names[i][1],names[i][2]),x+20,y+29,16,C.ink,500);text(tr('PAST INPUT · display-normalized','과거 입력 · 표시용 정규화'),x+20,y+49,11,C.muted);const vals=ch.effective,valid=vals.filter(finite),lo=Math.min(0,...valid),hi=Math.max(.001,...valid);const X=k=>x+20+k/35*(w-40),Y=v=>y+h-22-(v-lo)/(hi-lo||1)*62;
 line(vals.map((v,k)=>finite(v)?[X(k),Y(v)]:null),i===3?C.gold:C.mint,2);vals.forEach((v,k)=>{if(finite(v)&&!ch.observed[k]){ctx.fillStyle=C.gold;ctx.beginPath();ctx.arc(X(k),Y(v),2,0,7);ctx.fill();}});
 }
}
function draw(){if(!DATA)return;const c=DATA.cases[chosen],m=metrics(c),t=progress*6;ctx.fillStyle=C.bg;ctx.fillRect(0,0,1600,900);
 text('VORAFuel',40,62,37,C.ink,650);text(tr('RELATION-AWARE FUEL FORECASTING','관측 관계 기반 연료 소비 예측'),42,91,13,C.muted,500);
 text(`${tr('SELECTED CASE','선정 사례')} 0${chosen+1}`,614,54,17,C.mint,600);text(tr('Lower bin error than RF','RF 대비 구간 오차 감소'),1112,42,13,C.muted);text(`${m.rf.toFixed(1)}%`,1110,88,37,C.mint,600);text(tr('Selected-window result','선정 구간 결과'),1343,80,13,C.muted);
 line([[40,117],[1560,117]],C.grid);route(c,t);chart(c,t);inputs(c);
 text(tr('Saved predictions · evaluation-only GT and track · private scales withheld','저장 예측 재생 · 미래 정답과 항적은 평가용 · 원자료 척도 비공개'),42,839,14,C.muted);
 text(tr('Post-hoc success examples, not aggregate performance evidence.','사후 선정한 성공 사례이며 전체 성능을 대표하지 않습니다.'),42,866,14,C.muted);
 text(`HYOBIN PARK  /  +${t.toFixed(1)} h`,1285,859,15,C.mint,500);$('#clock').value=`+${t.toFixed(1)} h`;$('#time').value=progress;
}
function setLang(l){lang=l;document.body.classList.toggle('ko',l==='ko');document.documentElement.lang=l;$('#en').setAttribute('aria-pressed',l==='en');$('#ko').setAttribute('aria-pressed',l==='ko');const v=$('#film');v.pause();v.src=`assets/vorafuel-${l}.mp4`;v.poster=`assets/poster-${l}.jpg`;$('#download').href=`assets/vorafuel-${l}.mp4`;draw();}
function select(i){chosen=i;progress=0;document.querySelectorAll('.tabs button').forEach((b,j)=>{b.classList.toggle('active',j===i);b.setAttribute('aria-pressed',i===j);});draw();}
function stop(){playing=false;$('#play').textContent='▶';}
function tick(now){if(playing&&DATA){progress=Math.min(1,progress+(now-last)/18000);draw();if(progress===1)stop();}last=now;requestAnimationFrame(tick);}requestAnimationFrame(tick);
$('#play').onclick=()=>{if(playing)stop();else{if(progress===1)progress=0;playing=true;$('#play').textContent='Ⅱ';}};$('#restart').onclick=()=>{stop();progress=0;draw();};$('#time').oninput=e=>{stop();progress=Number(e.target.value);draw();};$('#en').onclick=()=>setLang('en');$('#ko').onclick=()=>setLang('ko');$('#full').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('.stage').requestFullscreen();}catch{}};
window.renderFrame=(caseIndex,p,l='en')=>{chosen=caseIndex;progress=Math.max(0,Math.min(1,p));lang=l;draw();};
window.demoReady=false;
fetch('showcase.json').then(r=>{if(!r.ok)throw Error('data');return r.json();}).then(d=>{DATA=d;for(let i=0;i<d.cases.length;i++){const b=document.createElement('button');b.innerHTML=`<span>CASE 0${i+1}</span><small>−${metrics(d.cases[i]).rf.toFixed(1)}% MAE / RF</small>`;b.onclick=()=>select(i);$('.tabs').append(b);}setLang(lang);select(0);window.demoReady=true;}).catch(()=>{$('#loadError').hidden=false;$('#loadError').textContent=tr('Unable to load demo data. Serve this page over HTTP and reload.','데모 자료를 불러오지 못했습니다. HTTP 서버로 열고 다시 시도해 주세요.');});
