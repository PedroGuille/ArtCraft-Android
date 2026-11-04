"""Pinned document proofing data, kept separate from the Spanish UI catalogs."""
from pathlib import Path
import hashlib,os,subprocess,tempfile
from .core import legacy,pipeline

def prepare(snapshot,prepared,state):
 if 'wordcraft' not in prepared:return None
 spec=snapshot['engine_lock']['translations'];commit=spec['source_commit']
 if not pipeline.SHA.fullmatch(commit):raise ValueError('Revisión de datos lingüísticos inválida.')
 cache=state/'cache/proofing';cache.mkdir(parents=True,exist_ok=True);checkout=cache/commit
 if checkout.is_symlink():raise ValueError('La caché lingüística no puede ser un enlace.')
 if not checkout.exists():
  with tempfile.TemporaryDirectory(prefix='.language-data-',dir=cache) as tmp:
   source=Path(tmp)/'checkout';pipeline.clone_commit(spec['repository'],commit,source);os.replace(source,checkout)
 actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
 if actual!=commit or legacy.source_hash(checkout)!=hashlib.sha256(b'').hexdigest():
  raise ValueError('Los datos lingüísticos fueron modificados. Conservá esos cambios fuera de la caché antes de continuar.')
 data=checkout/'language-data'
 if not data.is_dir():return None  # Older WordCraft revisions did not have this input.
 if not data.resolve().is_relative_to(checkout.resolve()):raise ValueError('Datos lingüísticos fuera de su revisión.')
 target=prepared['wordcraft']/'lucy/.cache/spanish-i18n-build/language-data';target.parent.mkdir(parents=True,exist_ok=True)
 if target.is_symlink():
  if target.resolve()!=data.resolve():target.unlink()
 elif target.exists():raise ValueError('Se conserva una carpeta de datos lingüísticos que no pertenece al constructor: '+str(target))
 if not target.exists():target.symlink_to(data,target_is_directory=True)
 return checkout

def add_notices(checkout,artifacts):
 if checkout is None:return
 destination=artifacts/'wordcraft/notices/craft-i18n'
 pipeline.copy_notice_tree(checkout/'language-data',destination/'language-data')
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
 pipeline.json_file(destination/'PROOFING-DATA.json',{'repository':'storytold/craft-i18n','source_commit':commit,'purpose':'Document proofing; interface catalogs remain Spanish only.'})
