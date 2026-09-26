"""Prepare an explicitly assumed display-sRGB adapter for the original Fuji LUT.
This is a candidate, not a measured inverse of Canon's tone/rendering pipeline.
No camera I/O, image editing, or automatic registration.
"""
from pathlib import Path
import argparse
import numpy as np
import json,hashlib
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('source',type=Path,help='Official F-Log2 → Classic Neg 65³ CUBE obtained by the user')
ap.add_argument('output',type=Path,help='New output CUBE file, 33³')
ap.add_argument('--report',type=Path,help='Optional new JSON report')
args=ap.parse_args()
source=args.source
assert hashlib.sha256(source.read_bytes()).hexdigest()=='f890a58d2ae278703aa09e73d6037a32cb925a6d90414292da7675e12b7dd3c9'
a=[]
for line in source.read_text().splitlines():
 s=line.strip()
 if not s or s.startswith('#') or s.startswith('LUT_'):continue
 v=[float(x) for x in s.split()];assert len(v)==3;a.append(v)
table=np.array(a).reshape(65,65,65,3)
assert np.isfinite(table).all()
def mat(prim):
 xy=np.array(prim);xyz=np.array([xy[:,0]/xy[:,1],np.ones(3),(1-xy.sum(1))/xy[:,1]])
 white=np.array([.3127/.329,1,(1-.3127-.329)/.329]);return xyz@np.diag(np.linalg.solve(xyz,white))
m=np.linalg.solve(mat([[.708,.292],[.170,.797],[.131,.046]]),mat([[.64,.33],[.30,.60],[.15,.06]]))
assert np.max(abs(m@np.ones(3)-1))<1e-12
def flog2(x):
 return np.where(x>=.000889,.245281*np.log10(5.555556*np.maximum(x,0)+.064829)+.384316,8.799461*x+.092864)
assert np.max(abs(flog2(np.array([0,.18,.9]))*1023-np.array([95,400,570])))<1

def sample(x):
 x=np.clip(x,0,1)*64;lo=np.floor(x).astype(int);hi=np.minimum(lo+1,64);f=x-lo;out=np.zeros_like(x)
 for b in range(2):
  for g in range(2):
   for r in range(2):
    w=(f[:,0] if r else 1-f[:,0])*(f[:,1] if g else 1-f[:,1])*(f[:,2] if b else 1-f[:,2])
    out+=table[(hi if b else lo)[:,2],(hi if g else lo)[:,1],(hi if r else lo)[:,0]]*w[:,None]
 return out

def transform(rgb):
 # Viewing RGB is treated as linear reflection after sRGB decoding. This does
 # not recover highlight information or undo a camera's scene-to-display curve.
 linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
 log=flog2(linear@m.T);gamma22=sample(log)
 linout=np.maximum(gamma22,0)**2.2
 return np.clip(np.where(linout<=.0031308,12.92*linout,1.055*linout**(1/2.4)-.055),0,1)

grid=np.array([[r/32,g/32,b/32] for b in range(33) for g in range(33) for r in range(33)])
out=transform(grid);assert np.isfinite(out).all()
path=args.output
with path.open('x') as f:
 f.write('TITLE "Fuji Official NC - sRGB adapter candidate"\n# Original source: FUJIFILM GFX ETERNA 55 FLog2 to CLASSIC Neg 65 grid V1.00\n# Assumed sRGB decoding -> linear F-Gamut -> F-Log2 -> source LUT -> gamma2.2 to sRGB\n# Not calibrated to Canon internal table domain; no claim of Fuji body matching\nLUT_3D_SIZE 33\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
 for row in out:f.write(' '.join(f'{v:.9f}' for v in row)+'\n')
points=np.array([[.5,.5,.5],[.75,.25,.25],[.25,.75,.25],[.25,.25,.75],[.75,.75,.25],[.75,.25,.75],[.25,.75,.75]])
report={'originalSource':str(source),'originalSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sourceLutSize':65,'candidateLutSize':33,'candidate':str(path),'candidateSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'cameraDomainCalibrated':False,'assumption':'Decoded display-sRGB treated as scene linear reflection; cannot undo Canon rendering. Candidate only.','flog2Checks10bit':(flog2(np.array([0,.18,.9]))*1023).tolist(),'srgbLinearToFGamutMatrix':m.tolist(),'representativeRGB':points.tolist(),'representativeOutput':transform(points).tolist()}
if args.report:
 with args.report.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
