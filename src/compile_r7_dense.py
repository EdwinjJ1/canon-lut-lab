"""Local-process experiment: native 17-grid compilation. Never accesses camera."""
import argparse, ctypes as C, sys, json, hashlib, struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cfp_bridge import Parser
libpath=Path('/Applications/Canon Utilities/EOS Utility/EU3/EOS Utility 3.app/Contents/PlugIns/EdsCFParse.bundle/Contents/MacOS/EdsCFParse')
args_parser=argparse.ArgumentParser(description=__doc__)
args_parser.add_argument('--camera-data',type=Path,required=True)
args_parser.add_argument('--out',type=Path,required=True)
args_parser.add_argument('pf3',nargs='+',type=Path)
args=args_parser.parse_args()
args.out.mkdir(parents=True,exist_ok=False)
EXPECTED_LIBRARY_SHA256='f4f2f931c174bfb200fde98d26c0e35c6bcaa3cf2374dbf89583bbeb7fe866b5'
if hashlib.sha256(libpath.read_bytes()).hexdigest()!=EXPECTED_LIBRARY_SHA256:
 raise RuntimeError('Installed parser changed; ABI must be checked again')
p=Parser(libpath);lib=p.lib;syslib=C.CDLL(None);P=C.c_void_p;U=C.c_uint32
read= getattr(lib,'_ZN13CProfileMaker15GetLutFileParamEiPPN4MLib15tagPSE_FILE_LUTE');read.argtypes=[P,C.c_int,C.POINTER(P)];read.restype=U
convert=lib.MLIBcalcLuckyFromFileLUT;convert.argtypes=[P,U,U,P];convert.restype=None
syslib.free.argtypes=[P]
vtable=C.cast(getattr(lib,'_ZTV16CProfileMakerPF3'),P).value
slot=C.c_void_p.from_address(vtable+16+32);original=slot.value
expected=C.cast(getattr(lib,'_ZN16CProfileMakerPF323MakeSecondLuckyTable17GEiPN4MLib17tagPSE_LUCKY_3D_2E'),P).value
assert original==expected
log=[]
@C.CFUNCTYPE(U,P,C.c_int,P)
def dense(self,index,out):
 source=P()
 try:
  if index not in (1,2):raise ValueError('Unexpected grid index')
  rc=read(self,index,C.byref(source))
  if not rc or not source.value:raise ValueError('Native dense table read failed')
  if C.string_at(source,6)!=struct.pack('<HHH',12,3,33):raise ValueError('Unexpected source header')
  C.memmove(out,struct.pack('<4I',3,17,0x1cc98,2),16)
  convert(source,0,index,out)
  data=(C.c_double*(4913*3)).from_address(out+16)
  import math
  if not all(math.isfinite(v) and 0<=v<=256 for v in data):raise ValueError('Invalid native intermediate')
  log.append({'index':index,'native_read':rc,'finite':True,'min':min(data),'max':max(data),'sha256':hashlib.sha256(C.string_at(out,16+0x1cc98)).hexdigest()})
  return 1
 except Exception as e:
  log.append({'error':str(e)});return 0
 finally:
  if source.value:syslib.free(source)
def native(name,args,rest=U):
 f=getattr(lib,name);f.argtypes=args;f.restype=rest;return f
ctor=native('_ZN16CProfileMakerPF3C1ERNSt3__16vectorIP8CPseItemNS0_9allocatorIS3_EEEE',[P,P],None)
build=native('_ZN13CProfileMaker17MakeLackyTable17GEv',[P])
internalGet=native('_ZN13CPseInterface15GetPropertyDataE9PseDataIDjPv12EdsByteOrder',[P,U,U,P,U])
compactBuild=native('_ZN16CProfileMakerPF323MakeLackyTableFrom3DLutEv',[P])
cipher=native('_Z12CipherBufferPhmm',[P,C.c_ulong,C.c_ulong],None)
def pointer(at):return C.c_void_p.from_address(at).value
def checktype(obj,symbol):
 if pointer(obj)!=C.cast(getattr(lib,symbol),P).value+16:raise ValueError('Unexpected ABI type: '+symbol)
def sections(interface):
 ans=[]
 for prop,seed in [(0x1f00,0xb8ed),(0x1f01,0x33137),(0x1022,0xb8ed),(0x102a,0x33137)]:
  buf=C.create_string_buffer(0x4cc4);rc=internalGet(interface,prop,len(buf),buf,0x4949)
  if rc:raise ValueError('Native internal table read failed '+str(rc))
  cipher(buf,len(buf),seed);ans.append(bytes(buf))
 return ans
try:
 for path in args.pf3:
  name=path.stem
  r=p.open(Path(path));begin=len(log)
  try:
   for key,file in [(0x01000001,'property-01000001-param-0.bin'),(0x01000210,'property-01000210-param-0.bin')]:
    data=(args.camera_data/file).read_bytes();buf=C.create_string_buffer(data);p.call('SetPropertyData',r,key,0,len(data),buf)
   data=p.get(r,0x01000203)
   if len(data)!=83076:raise ValueError('Unexpected R7 payload length')
   checktype(r.value,'_ZTV9CEdsParse')
   fileparser=pointer(r.value+0x38);checktype(fileparser,'_ZTV17CEdsFileParserPSE')
   interface=pointer(fileparser+0x30);checktype(interface,'_ZTV17CPseInterfaceVer3')
   stock=sections(interface);offsets=[data.find(x) for x in stock]
   stockAux=C.create_string_buffer(4096)
   if internalGet(interface,0x1f02,4096,stockAux,0x4949):raise ValueError('Stock auxiliary read failed')
   cipher(stockAux,4096,0xb8ed)
   auxOffset=data.find(stockAux.raw)
   if auxOffset!=78980 or data.count(stockAux.raw)!=1:raise ValueError('Auxiliary carrier match failed')
   if any(o<0 or data.count(x)!=1 for o,x in zip(offsets,stock)):raise ValueError('Stock sections do not uniquely match native payload')
   obj=C.create_string_buffer(24);ctor(obj,pointer(interface+8))
   ownvtable=C.create_string_buffer(C.string_at(vtable+16,0x70))
   C.c_void_p.from_buffer(ownvtable,32).value=C.cast(dense,P).value
   C.c_void_p.from_buffer(obj).value=C.addressof(ownvtable)
   if build(obj)!=1:raise ValueError('Native builder failed')
   if [x.get('index') for x in log[begin:]] != [1,2]:raise ValueError('Both grid callbacks required')
   new=sections(interface);payload=bytearray(data)
   for o,x in zip(offsets,new):payload[o:o+len(x)]=x
   if compactBuild(obj)!=1:raise ValueError('Native compact-grid conversion failed')
   aux=C.create_string_buffer(4096)
   if internalGet(interface,0x1022,4096,aux,0x4949):raise ValueError('Native compact-grid read failed')
   cipher(aux,4096,0xb8ed)
   payload[auxOffset:auxOffset+4096]=aux.raw
   # Match the observed EOS Utility outer header; preserve inner style title.
   payload[8:40]=bytes(32)
   out=args.out/(name+'.bin');out.write_bytes(payload)
   print(json.dumps({'name':name,'size':len(payload),'section_offsets':offsets,'auxiliary_offset':auxOffset,'auxiliary_sha256':hashlib.sha256(aux.raw).hexdigest(),'sha256':hashlib.sha256(payload).hexdigest(),'grids':log[begin:]}),flush=True)
  finally:p.call('Release',r)
finally:p.call('Terminate')
