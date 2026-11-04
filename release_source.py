#!/usr/bin/env python3
"""Create the source distribution without toolchains, outputs or private keys."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED,ZipInfo
import hashlib,json

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dist';OUT.mkdir(exist_ok=True)
path=OUT/'Lucy-Builder-2.1.1-source.zip'
blocked={'dist','build','target','.git','.flatpak-builder','repo','__pycache__','cache','work','.cache'}
with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=9) as archive:
 for file in sorted(ROOT.rglob('*')):
  rel=file.relative_to(ROOT)
  if not file.is_file() or file.is_symlink() or any(part in blocked for part in rel.parts) or file.suffix in {'.pyc','.p12','.pfx','.jks','.keystore','.apk','.flatpak'}:continue
  entry=ZipInfo('Lucy-Builder-2.1.1/'+rel.as_posix(),date_time=(2026,11,2,0,0,0));entry.compress_type=ZIP_DEFLATED;entry.external_attr=(file.stat().st_mode&0xffff)<<16;archive.writestr(entry,file.read_bytes(),compress_type=ZIP_DEFLATED,compresslevel=9)
files=[OUT/'Lucy-Builder-2.1.1-x86_64.flatpak',path]
(OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
print(path,path.stat().st_size)
