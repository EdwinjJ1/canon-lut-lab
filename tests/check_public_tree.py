"""Fail on accidental large/binary camera or user assets in the public tree."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
forbidden={'.pf3','.bin','.cube','.cr3','.jpg','.jpeg','.zip','.dmg','.pkg'}
paths=[p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and 'build' not in p.parts and 'local' not in p.parts and '__pycache__' not in p.parts]
for p in paths:
    assert p.suffix.lower() not in forbidden,p
    assert p.stat().st_size<250_000,p
    if p.suffix.lower() in {'.md','.py','.m','.js','.cjs','.sh','.yml','.json'}:
        text=p.read_text(errors='ignore')
        assert not re.search('/Us' + r'ers/[^/\s]+/',text),p
        assert not re.search(r'gh[opurs]_[A-Za-z0-9]{20,}',text),p
print(f'Checked {len(paths)} public source/documentation files')
