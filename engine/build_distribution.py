from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED,ZipInfo
import os,io,base64,hashlib
source=Path(__file__).resolve().parent;r=source;buffer=io.BytesIO()
exclude={'.git','.cache','build','dist','target','__pycache__','node_modules','.gradle','signing','Lucy-output'}
root_files={'bootstrap.py','lucy.py','lucy.sh','build_distribution.py','LEEME.md','VALIDACION.md','LICENSE'}
root_dirs={'pipeline','tests'}
with ZipFile(buffer,'w',ZIP_DEFLATED,compresslevel=9) as z:
 for folder,dirs,files in os.walk(source):
  if Path(folder)==source:
   dirs[:]=[d for d in dirs if d in root_dirs];files=[n for n in files if n in root_files]
  dirs[:]=sorted(d for d in dirs if d not in exclude and not (Path(folder,d)/'.lucy-output.json').exists() and not (Path(folder,d)/'build.lock').exists() and not (Path(folder).relative_to(source).as_posix()=='pipeline/lucy/app/src/main/assets' and d=='engines'))
  for name in sorted(files):
   p=Path(folder)/name
   if p.suffix in {'.apk','.jks','.keystore','.p12','.pfx','.wasm','.class','.pyc'}:continue
   info=ZipInfo('Lucy-Builder-Linux-1.0.0/'+p.relative_to(source).as_posix(),(2026,10,31,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=0o100644<<16
   z.writestr(info,p.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
payload=buffer.getvalue();sha=hashlib.sha256(payload).hexdigest()
header='''#!/usr/bin/env bash
set -e
lucy_python="$(command -v python3 || true)"
if [[ -z "$lucy_python" ]]; then
  echo 'Instalá Python: Fedora: sudo dnf install python3 | Ubuntu/Debian: sudo apt install python3' >&2
  exit 1
fi
"$lucy_python" - "$0" "$@" 3<&0 <<'LUCY_BOOTSTRAP'
import sys, pathlib, base64, hashlib, io, zipfile, tempfile, runpy, stat, os
if sys.version_info < (3,11): raise SystemExit('Se necesita Python 3.11 o posterior.')
script=pathlib.Path(sys.argv[1]);marker=b'\\n__LUCY_PAYLOAD__\\n'
raw=script.read_bytes();payload=base64.b64decode(b''.join(raw.split(marker,1)[1].split()),validate=True)
if hashlib.sha256(payload).hexdigest() != 'PAYLOAD_SHA': raise SystemExit('El constructor está incompleto o dañado; descargalo de nuevo.')
with tempfile.TemporaryDirectory(prefix='lucy-builder-') as tmp:
    base=pathlib.Path(tmp)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries=archive.infolist()
        if len(entries)>3000 or sum(e.file_size for e in entries)>64*1024*1024: raise SystemExit('Paquete demasiado grande.')
        for entry in entries:
            path=pathlib.PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(entry.external_attr>>16): raise SystemExit('Ruta no válida en el constructor.')
        archive.extractall(base)
    root=base/'Lucy-Builder-Linux-1.0.0'
    sys.stdin=os.fdopen(3,'r',closefd=False)
    sys.path.insert(0,str(root));sys.argv=[str(root/'lucy.py'),*sys.argv[2:]]
    runpy.run_path(str(root/'lucy.py'),run_name='__main__')
LUCY_BOOTSTRAP
exit "$?"
__LUCY_PAYLOAD__
'''.replace('PAYLOAD_SHA',sha)
out=r/'dist';out.mkdir(exist_ok=True)
(out/'Lucy-Builder-Linux-1.0.0.zip').write_bytes(payload)
(out/'Lucy-Builder-Linux-1.0.0.run').write_bytes(header.encode()+base64.encodebytes(payload))
(out/'Lucy-Builder-Linux-1.0.0.run').chmod(0o755)
print('Packaged Linux constructor:',len(payload),'source ZIP bytes')
