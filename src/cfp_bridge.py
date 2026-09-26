"""Experimental macOS PF3 file bridge. Never connects to or writes to a camera.

Requires a locally installed Canon EdsCFParse bundle, licensed by the user.
A PSE-exported baseline is mandatory. Camera transport is still unverified. Round-trip validation only proves
file serialization; it does not prove camera acceptance or correct rendering.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import sys
import subprocess
import tempfile
import shutil

# Research property IDs; lengths below describe old fixtures only.
# Runtime lengths must be read from Canon's parser; they vary across valid files.
SCHEMA = [(0x114, 4), (0x115, 32), (0x40001002, 32),
          (0x4000100a, 64), (0x40001021, 240), (0x40001029, 240),
          (0x40001019, 300), (0x40001018, 300), (0x40001065, 300),
          (0x40001061, 512), (0x40001062, 512), (0x40001023, 8),
          (0x4000102b, 8), (0x40001008, 456), (0x40001012, 4),
          (0x40001070, 215628), (0x40001071, 215628),
          (0x4000100d, 3), (0x4000100c, 2), (0x40001011, 4), (0x40001080, 4)]


class Parser:
    def __init__(self, library):
        if sys.platform != 'darwin':
            raise RuntimeError('This bridge targets macOS only')
        self.lib = C.CDLL(str(library.resolve()))
        u, p = C.c_uint32, C.c_void_p
        signatures = {
            'Initialize': [], 'Terminate': [],
            'CreateRef': [C.c_char_p, u, u, C.POINTER(p)],
            'Release': [p], 'ReflectProperty': [p],
            'GetPropertySize': [p, u, u, C.POINTER(u), C.POINTER(u)],
            'GetPropertyData': [p, u, u, u, p],
            'SetPropertyData': [p, u, u, u, p]}
        for name, args in signatures.items():
            f = getattr(self.lib, 'EdsCfp' + name)
            f.argtypes, f.restype = args, u
        self.call('Initialize')

    def call(self, name, *args):
        result = getattr(self.lib, 'EdsCfp' + name)(*args)
        if result:
            raise RuntimeError('%s failed: 0x%08x' % (name, result))

    def open(self, path, write=False, existing=False):
        ref = C.c_void_p()
        self.call('CreateRef', str(path.resolve()).encode('utf-8'),
                  1 if write and not existing else 2, 2 if write and existing else (1 if write else 0), C.byref(ref))
        if not ref.value:
            raise RuntimeError('Null Canon reference')
        return ref

    def get(self, ref, prop, expected=None):
        kind, size = C.c_uint32(), C.c_uint32()
        self.call('GetPropertySize', ref, prop, 0, C.byref(kind), C.byref(size))
        if expected is not None and size.value != expected:
            raise RuntimeError('Unexpected property size for 0x%08x: %d' % (prop, size.value))
        if not 0 < size.value <= 1048576:
            raise RuntimeError("Invalid property size")
        data = (C.c_ubyte * size.value)()
        self.call('GetPropertyData', ref, prop, 0, size.value, data)
        return bytes(data)

    def read(self, path):
        ref = self.open(path)
        try:
            return {key: self.get(ref, key) for key, size in SCHEMA}
        finally:
            self.call('Release', ref)


def validate_table(table):
    if len(table) != 215628 or struct.unpack_from('<HHH', table) != (12, 3, 33):
        raise ValueError('Expected a 33-grid, 3-channel, 12-bit research table')
    if any(value > 4095 for (value,) in struct.iter_unpack('<H', table[6:])):
        raise ValueError('Table component exceeds 12-bit range')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=Path('/Applications/Canon Utilities/EOS Utility/EU3/EOS Utility 3.app/Contents/PlugIns/EdsCFParse.bundle/Contents/MacOS/EdsCFParse'))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--table', type=Path)
    source.add_argument('--cube', type=Path, help='Pure 3D CUBE, converted by the included core.js')
    parser.add_argument('--strength', type=float, default=1.0, help='CUBE strength between 0 and 1')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base', type=Path, required=True, help='Required original PF3 exported by Canon PSE; zero-filled generated bases are rejected')
    parser.add_argument('--title', default='R7 LUT Test')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose a new file')
    if not args.output.parent.is_dir():
        parser.error('Output parent must exist')
    if not 0 <= args.strength <= 1:
        parser.error('Strength must be between 0 and 1')
    if args.table and args.strength != 1:
        parser.error('Strength applies to CUBE input only')
    if args.cube:
        js = "const fs=require('fs'),L=require(process.argv[1]);const x=L.parse(fs.readFileSync(process.argv[2],'utf8'));process.stdout.write(Buffer.from(L.tableBytes(L.resample(x,Number(process.argv[3])))));"
        result = subprocess.run(['node', '-e', js, str(Path(__file__).resolve().parent.parent / 'core.js'), str(args.cube.resolve()), str(args.strength)], capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError('CUBE conversion failed: ' + result.stderr.decode(errors='replace'))
        table = result.stdout
    else:
        table = args.table.read_bytes()
    validate_table(table)
    title = args.title.encode('ascii', errors='strict')
    if not 1 <= len(title) <= 31:
        parser.error('Title must be 1–31 ASCII bytes')
    temp = tempfile.TemporaryDirectory(prefix='.pf3-check-', dir=args.output.parent)
    staged = Path(temp.name) / args.output.name
    api = None
    try:
        api = Parser(args.library)
        props = api.read(args.base)
        # A serializable zero-filled structure is not a valid native baseline.
        for key in (0x40001019, 0x40001018, 0x40001065, 0x40001008):
            if not any(props[key]):
                raise ValueError('Rejected zero-filled generated base; export a fresh PF3 with Canon PSE')
        for key in (0x40001070, 0x40001071):
            validate_table(props[key])
        # Compose in the table's numeric domain. Its relation to camera color
        # space is unverified; this remains an offline research experiment.
        compose_js = """const fs=require('fs'),L=require(process.argv[1]);
const q=JSON.parse(fs.readFileSync(0,'utf8')),t=Buffer.from(q.transform,'hex');
const data=new Float64Array(33**3*3);
for(let r=0;r<33;r++)for(let g=0;g<33;g++)for(let b=0;b<33;b++)for(let c=0;c<3;c++)
data[((b*33+g)*33+r)*3+c]=t.readUInt16LE(6+((r*33+g)*33+b)*6+c*2)/4095;
const lut=q.cube ? L.parse(q.cube) : {size:33,min:[0,0,0],max:[1,1,1],data};
const out=Buffer.from(q.base,'hex');
for(let i=6;i<out.length;i+=6){const rgb=[0,1,2].map(c=>out.readUInt16LE(i+c*2)/4095);
L.transform(lut,rgb,q.cube ? q.strength : 1).forEach((v,c)=>out.writeUInt16LE(Math.round(Math.max(0,Math.min(1,v))*4095),i+c*2));}
process.stdout.write(out);"""
        for key in (0x40001070, 0x40001071):
            if args.strength == 0:
                continue
            result = subprocess.run(['node', '-e', compose_js,
                str(Path(__file__).resolve().parent.parent / 'core.js')],
                input=json.dumps({'transform': table.hex(), 'base': props[key].hex(),
                    'cube': args.cube.read_text() if args.cube else None,
                    'strength': args.strength}).encode(),
                capture_output=True, timeout=60)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors='replace'))
            validate_table(result.stdout)
            props[key] = result.stdout
        props[0x40001002] = title.ljust(32, b'\0')
        shutil.copyfile(args.base, staged)
        ref = api.open(staged, write=True, existing=True)
        try:
            for key in (0x40001002, 0x40001070, 0x40001071):
                blob = C.create_string_buffer(props[key], len(props[key]))
                api.call('SetPropertyData', ref, key, 0, len(props[key]), blob)
            api.call('ReflectProperty', ref)
        finally:
            api.call('Release', ref)
        actual = api.read(staged)
        if actual != props:
            raise RuntimeError('PF3 property round-trip mismatch; do not register output')
        data = staged.read_bytes()
        if not 430000 <= len(data) <= 1048576:
            raise RuntimeError('Unexpected PF3 size; output not published')
        # Exclusive create avoids overwriting an output made during conversion.
        with args.output.open('xb') as output:
            output.write(data)
        print(json.dumps({'status': 'file_round_trip_passed', 'bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest(),
                          'experimental_generated_base': False,
                          'base_sha256': hashlib.sha256(args.base.read_bytes()).hexdigest(),
                          'camera_installation_allowed': False,
                          'camera_validated': False}, indent=2))
    finally:
        try:
            if api is not None:
                api.call('Terminate')
        finally:
            temp.cleanup()


if __name__ == '__main__':
    main()
