const assert=require('node:assert/strict');
const test=require('node:test');
const L=require('./core.js');
const near=(a,b,e=1e-8)=>a.forEach((v,i)=>assert.ok(Math.abs(v-b[i])<e,`${a} != ${b}`));
test('CUBE red-fastest order verified using explicit two-grid fixture',()=>{
  const t=L.parse('LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1');
  near(L.sample(t,[.21,.63,.85]),[.21,.63,.85]);
});
test('identity and trilinear interior / endpoint values',()=>{
  const t=L.diagnostic('identity');for(const p of [[0,0,0],[1,1,1],[1,0,0],[0,0,1],[.13,.61,.99]]) near(L.sample(t,p),p);
});
test('channel swap distinguishes LUT from base Picture Style',()=>near(L.sample(L.diagnostic('swap'),[.8,.4,.1]),[.1,.4,.8]));
test('nonlinear cross-channel polynomial interpolates independently at random points',()=>{
  const fn=([r,g,b])=>[r*g,g*b,r*b];const lut=L.make(3,fn,'cross');
  for(let i=0;i<30;i++){const p=[(i*.13)%1,(i*.37)%1,(i*.61)%1];near(L.sample(lut,p),fn(p));}
});
test('domain normalization and out-of-domain clamp',()=>{
  const t=L.diagnostic('identity');t.min=[-1,0,2];t.max=[1,2,4];near(L.sample(t,[0,1,3]),[.5,.5,.5]);near(L.sample(t,[-9,9,9]),[0,1,1]);
});
test('strength and output clipping',()=>{
  near(L.transform(L.diagnostic('swap'),[1,.2,0],0),[1,.2,0]);near(L.transform(L.diagnostic('swap'),[1,.2,0],.25),[.75,.2,.25]);
  near(L.transform(L.make(2,()=>[-1,2,.5],'clip'),[0,0,0]),[0,1,.5]);
});
test('quantized identity is bounded within half a 12-bit code at nodes',()=>{
  const t=L.resample(L.diagnostic('identity'));
  for(let i=0;i<33;i++){const p=[i/32,(32-i)/32,0.5];near(L.sample(t,p),p,0.5/4095+1e-10);}
});
test('CUBE serialization roundtrip',()=>{
  const t=L.diagnostic('warm'),r=L.parse(L.cubeText(t));near(L.sample(t,[.12,.56,.89]),L.sample(r,[.12,.56,.89]));
});
test('research table header, length and blue-fastest storage',()=>{
  const b=L.tableBytes(L.resample(L.diagnostic('identity'))),v=new DataView(b.buffer);
  assert.equal(b.length,215628);assert.deepEqual([0,2,4].map(i=>v.getUint16(i,true)),[12,3,33]);
  assert.deepEqual([6,8,10].map(i=>v.getUint16(i,true)),[0,0,0]);
  assert.deepEqual([12,14,16].map(i=>v.getUint16(i,true)),[0,0,128]);
  assert.deepEqual([6+32*6,8+32*6,10+32*6].map(i=>v.getUint16(i,true)),[0,0,4095]);
});
test('reject unsupported, malformed, duplicate and nonfinite CUBE input',()=>{
  for(const text of ['LUT_1D_SIZE 2','LUT_3D_SIZE 1','LUT_3D_SIZE 1000','LUT_3D_SIZE 2\n0 0 0','LUT_3D_SIZE 2\nNaN 0 0','LUT_3D_SIZE 2\nLUT_3D_SIZE 2','FOO 1 2'])assert.throws(()=>L.parse(text));
  assert.throws(()=>L.parse(L.cubeText(L.diagnostic('identity')).replace('DOMAIN_MAX 1 1 1','DOMAIN_MAX 0 1 1')));
});
