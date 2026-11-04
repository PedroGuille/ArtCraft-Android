"""Verify nested JavaScript/WASM dependencies that the current egui web runtime imports."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[1]/'app/src/main/assets/engines'
for folder in sorted(p for p in root.iterdir() if p.is_dir()):
 manifest=json.loads((folder/'folio-engine.json').read_text())
 for name,expected in manifest['files'].items():
  p=folder/name
  assert p.resolve().is_relative_to(folder.resolve()),name
  assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
 imports=set()
 for p in folder.rglob('*.js'):
  for relative in re.findall(r'(?:from\s*|import\s*)[\'"](\./[^\'"]+)[\'"]',p.read_text()):
   target=(p.parent/relative).resolve();assert target.is_relative_to(folder.resolve()) and target.is_file(),(p.name,relative)
   imports.add(str(target.relative_to(folder.resolve())))
 assert any(name.startswith('snippets/') for name in imports),(folder.name,'missing current eframe inline runtime')
 assert re.search(r'<html[^>]*lang="es"',(folder/'index.html').read_text())
 print('PASS:',folder.name, 'all local module imports are packaged, including',len(imports),'nested runtime dependency/dependencies')
