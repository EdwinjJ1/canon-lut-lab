"""Analyze photographed JPEGs against a CUBE; does not produce edited images."""
from pathlib import Path
from PIL import Image,ExifTags
import numpy as np,json,argparse,hashlib

p=argparse.ArgumentParser();p.add_argument('base',type=Path);p.add_argument('actual',type=Path);p.add_argument('--repeat',type=Path);p.add_argument('--cube',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
def read(f):
 im=Image.open(f);ex=im.getexif().get_ifd(34665);data=np.asarray(im.resize((960,640)),dtype=float)/255
 return data,{'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':im.size,'exposure':{ExifTags.TAGS.get(k,k):str(v) for k,v in ex.items() if k in [33434,33437,34855,37380,41987]}}
rows=[];n=None
for line in a.cube.read_text().splitlines():
 s=line.split('#')[0].strip()
 if not s:continue
 if s.startswith('LUT_3D_SIZE'):n=int(s.split()[1]);continue
 if s.startswith(('TITLE','DOMAIN_')):continue
 rows.append([float(x) for x in s.split()])
lut=np.array(rows).reshape(n,n,n,3)
def sample(rgb):
 shape=rgb.shape;x=np.clip(rgb.reshape(-1,3),0,1)*(n-1);lo=np.floor(x).astype(int);hi=np.minimum(lo+1,n-1);t=x-lo;out=np.zeros_like(x)
 for b in range(2):
  for g in range(2):
   for r in range(2):
    w=(t[:,0] if r else 1-t[:,0])*(t[:,1] if g else 1-t[:,1])*(t[:,2] if b else 1-t[:,2])
    out+=lut[(hi if b else lo)[:,2],(hi if g else lo)[:,1],(hi if r else lo)[:,0]]*w[:,None]
 return out.reshape(shape)
def stats(error):
 v=np.abs(error)*255
 return {'meanAbsRGBCodeError':v.mean(0).tolist(),'medianAbsRGBCodeError':np.median(v,0).tolist(),'p95AbsRGBCodeError':np.percentile(v,95,axis=0).tolist()}
b,br=read(a.base);t,tr=read(a.actual);y=b.mean(2);gradient=8*np.hypot(*np.gradient(y));mask=(gradient<.04)&(b.min(2)>.03)&(b.max(2)<.95)
repeat_report=None
if a.repeat:
 c,cr=read(a.repeat);repeat_report={'capture':cr,'difference':stats((b-c)[mask])}
# Diagnostic gamma-domain alternatives only, never accepted as calibration.
results=[]
for g in [0.45,0.6,0.8,1.,1.2,1.5,1.8,2.2,2.4]:
 expected=np.clip(sample(b**g),0,1)**(1/g)
 results.append({'assumedDomainGamma':g,'error':stats((expected-t)[mask])})
report={'base':br,'actual':tr,'sameExposure':br['exposure']==tr['exposure'],'flatPatchPixelCount':int(mask.sum()),'repeat':repeat_report,'domainCandidates':results,'baselineVsActual':stats((b-t)[mask]),'scope':'Numerical comparison requires matching stationary composition; not a colorimetric calibration and no pass threshold asserted.'}
a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
