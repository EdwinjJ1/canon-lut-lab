/* Original research/demo implementation. CUBE order: R fastest, then G, B. */
(function(root) {
  'use strict';
  const clamp = x => Math.max(0, Math.min(1, x));
  function parse(text) {
    if (text.length > 32*1024*1024) throw Error('LUT 文件超过 32 MB');
    let size, title='Imported LUT', min=[0,0,0], max=[1,1,1], rows=[];
    const seen=new Set();
    for (const [i,raw] of text.replace(/^\uFEFF/,'').split(/\r?\n/).entries()) {
      const line=raw.replace(/#.*$/,'').trim(); if (!line) continue;
      const p=line.split(/\s+/), key=p[0];
      if (key==='TITLE') { title=line.slice(5).trim().replace(/^"|"$/g,''); continue; }
      if (['LUT_3D_SIZE','DOMAIN_MIN','DOMAIN_MAX'].includes(key)) {
        if(seen.has(key)||rows.length) throw Error(`第 ${i+1} 行：重复或位置错误的头字段`);
        seen.add(key);
        if(key==='LUT_3D_SIZE') {
          size=Number(p[1]);
          if(p.length!==2||!Number.isInteger(size)||size<2||size>65) throw Error('仅支持 2–65 阶 3D CUBE');
        } else {
          const v=p.slice(1).map(Number);
          if(v.length!==3||v.some(x=>!Number.isFinite(x))) throw Error('DOMAIN 必须是三个有限数值');
          if(key==='DOMAIN_MIN') min=v; else max=v;
        }
        continue;
      }
      if(key==='LUT_1D_SIZE') throw Error('暂不支持 1D / shaper LUT，请先转换成纯 3D LUT');
      const v=p.map(Number);
      if(!size||v.length!==3||v.some(x=>!Number.isFinite(x))) throw Error(`第 ${i+1} 行：未知字段或无效 RGB 数据`);
      rows.push(...v); if(rows.length>size**3*3) throw Error('LUT 数据行数超过声明');
    }
    if(!size||rows.length!==size**3*3) throw Error('LUT 数据不完整，数量必须等于阶数的三次方');
    if(min.some((x,i)=>max[i]<=x)) throw Error('DOMAIN_MAX 必须大于 DOMAIN_MIN');
    return {size,title,min,max,data:Float64Array.from(rows)};
  }
  function sample(lut, rgb) {
    const n=lut.size, x=rgb.map((v,i)=>clamp((v-lut.min[i])/(lut.max[i]-lut.min[i]))*(n-1));
    const lo=x.map(Math.floor), hi=lo.map(v=>Math.min(n-1,v+1)), f=x.map((v,i)=>v-lo[i]), out=[0,0,0];
    for(let b=0;b<2;b++) for(let g=0;g<2;g++) for(let r=0;r<2;r++) {
      const w=(r?f[0]:1-f[0])*(g?f[1]:1-f[1])*(b?f[2]:1-f[2]);
      const j=(((b?hi[2]:lo[2])*n+(g?hi[1]:lo[1]))*n+(r?hi[0]:lo[0]))*3;
      for(let c=0;c<3;c++) out[c]+=lut.data[j+c]*w;
    }
    return out;
  }
  function make(size, fn, title) {
    const data=new Float64Array(size**3*3); let i=0;
    for(let b=0;b<size;b++) for(let g=0;g<size;g++) for(let r=0;r<size;r++)
      for(const x of fn([r/(size-1),g/(size-1),b/(size-1)])) data[i++]=x;
    return {size,title,min:[0,0,0],max:[1,1,1],data};
  }
  function transform(lut,rgb,amount=1) {const q=sample(lut,rgb);return rgb.map((v,i)=>clamp(v+(q[i]-v)*amount));}
  function resample(lut,amount=1) {
    return make(33,rgb=>transform(lut,rgb,amount).map(v=>Math.round(v*4095)/4095),lut.title+' / 33-grid 12-bit');
  }
  function cubeText(lut) {
    const a=[`TITLE "${lut.title.replace(/["\r\n]/g,' ')}"`,`LUT_3D_SIZE ${lut.size}`,'DOMAIN_MIN '+lut.min.join(' '),'DOMAIN_MAX '+lut.max.join(' ')];
    for(let i=0;i<lut.data.length;i+=3) a.push(Array.from(lut.data.slice(i,i+3),v=>v.toFixed(9)).join(' '));
    return a.join('\n')+'\n';
  }
  function diagnostic(kind) {
    const f={identity:v=>v,swap:([r,g,b])=>[b,g,r],mono:([r,g,b])=>{const y=.2126*r+.7152*g+.0722*b;return [y,y,y];},
      warm:([r,g,b])=>[clamp(r*1.045+.012),clamp(g*.99+.005),clamp(b*.92+.018)]};
    if(!f[kind]) throw Error('Unknown diagnostic');
    return make(17,f[kind],kind);
  }
  // Research table only, based on the observed PF3 property-table layout.
  // This is NOT a PF3 file, EDSDK payload, camera firmware, or installer.
  function tableBytes(lut) {
    if(lut.size!==33) throw Error('Research table requires 33-grid input');
    const buffer=new ArrayBuffer(6+33**3*6), v=new DataView(buffer);
    [12,3,33].forEach((x,i)=>v.setUint16(i*2,x,true));let o=6;
    for(let r=0;r<33;r++) for(let g=0;g<33;g++) for(let b=0;b<33;b++) {
      const j=((b*33+g)*33+r)*3;
      for(let c=0;c<3;c++){v.setUint16(o,Math.round(clamp(lut.data[j+c])*4095),true);o+=2;}
    } return new Uint8Array(buffer);
  }
  const api={parse,sample,make,transform,resample,cubeText,diagnostic,tableBytes};
  if(typeof module!=='undefined') module.exports=api; else root.LutLab=api;
})(typeof globalThis!=='undefined'?globalThis:this);
