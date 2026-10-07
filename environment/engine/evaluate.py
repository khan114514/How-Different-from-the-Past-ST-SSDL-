"""Public candidate evaluation: the owner lane sends bounded source, never scores."""
import argparse
import json
from pathlib import Path
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--solution',default='/workspace/solution')
args=parser.parse_args()
base=Path(args.solution)
if (base/'solve.sh').read_bytes()!=Path('/opt/forecast-engine/solve.sh').read_bytes():
    raise ValueError('Frozen solve.sh was altered; restore it before public evaluation')
files={}
for path in base.rglob('*.py'):
    relative=path.relative_to(base)
    if path.is_symlink() or any(part=='..' for part in relative.parts):
        raise ValueError('Source symlink or traversal refused')
    value=path.read_text()
    if len(value.encode())>1024**2:raise ValueError('Executable source file too large')
    files[str(relative)]=value
if 'method.py' not in files or len(files)>16 or sum(len(v.encode()) for v in files.values())>1536*1024:
    raise ValueError('Executable source bundle exceeds public evaluation limit')
body=json.dumps({'files':files}).encode()
operation=urllib.request.Request('http://127.0.0.1:8766/evaluate',data=body,headers={'Content-Type':'application/json'})
with urllib.request.urlopen(operation,timeout=1200) as response:
    status=response.status
    value=json.load(response)
print(json.dumps(value,ensure_ascii=False,indent=2))
if status!=200 or value.get('status')!='ok':raise SystemExit(1)
