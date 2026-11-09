"""Isolated, cancellable build worker. GUI input never becomes shell code."""
from pathlib import Path
from types import SimpleNamespace
import argparse,copy,fcntl,json,os,sys,time,uuid,urllib.error
from .catalog import BY_ID,OFFICE,selection
from .revisions import MODES
from .core import ROOT,legacy,bootstrap,pipeline
from . import host

VERSION='2.3.0'
def emit(kind,**fields):print('@LUCY '+json.dumps({'event':kind,**fields},ensure_ascii=False),flush=True)
def save(path,value):legacy.save_json(path,value)

def revision(app_id,mode):
 if mode in {'reviewed','verified'}:
  heads=json.loads((ROOT/'app'/('reviewed.json' if mode=='reviewed' else 'verified.json')).read_text())['heads']
  if app_id not in heads:raise ValueError('No hay una versión guardada para '+app_id)
  return heads[app_id]
 repo=BY_ID[app_id].repository
 if mode=='main':return pipeline.latest(repo)
 try:release=json.loads(pipeline.get('https://api.github.com/repos/'+repo+'/releases/latest'))
 except urllib.error.HTTPError as error:
  if error.code==404:raise ValueError('No hay una publicación disponible para '+app_id+'. Elegí versiones base o main.') from None
  raise
 tag=release.get('tag_name','')
 if not tag or any(c.isspace() for c in tag):raise ValueError('No hay una publicación válida para '+app_id)
 rows=pipeline.run(['git','ls-remote','https://github.com/'+repo+'.git','refs/tags/'+tag,'refs/tags/'+tag+'^{}'],capture=True).splitlines()
 refs={line.split()[1]:line.split()[0] for line in rows if len(line.split())==2}
 commit=refs.get('refs/tags/'+tag+'^{}') or refs.get('refs/tags/'+tag)
 if not commit or not pipeline.SHA.fullmatch(commit):raise ValueError('No se pudo fijar la publicación '+tag)
 return commit

def resolve(ids,mode,language_mode='all'):
 base=json.loads((pipeline.TEMPLATE/'engine-lock.json').read_text());lock=copy.deepcopy(base)
 verified=json.loads((ROOT/'app'/('reviewed.json' if mode=='reviewed' else 'verified.json')).read_text())
 heads={name:revision(name,mode) for name in ids}
 lock['language_mode']=language_mode;lock['ui_languages']=['all-upstream'] if language_mode=='all' else ['es']
 lock['engines']=[e for e in lock['engines'] if e['id'] in ids]
 for engine in lock['engines']:
  engine['language_mode']=language_mode;engine['language_adapter_sha256']=bootstrap.digest(ROOT/'engine/pipeline/languages.py');engine['adapter_base_commit']=engine['source_commit'];engine['source_commit']=heads[engine['id']];engine['source_branch']='main';engine.pop('source_date',None)
 if mode in {'reviewed','verified'}:
  lock['fonts']=copy.deepcopy(verified['fonts']);lock['translations']=copy.deepcopy(verified['translations'])
 else:
  lock['fonts']['source_commit']=pipeline.latest('storytold/craft-fonts')
  if 'wordcraft' in ids:
   rev=pipeline.get('https://raw.githubusercontent.com/storytold/wordcraft/'+heads['wordcraft']+'/craft-i18n.rev').decode().strip()
   if not pipeline.SHA.fullmatch(rev):raise ValueError('Revisión de traducción inválida.')
   lock['translations']['source_commit']=rev
   for file in lock['translations']['files']:
    import hashlib
    lock['translations']['files'][file]=hashlib.sha256(pipeline.get('https://raw.githubusercontent.com/storytold/craft-i18n/'+rev+'/'+file)).hexdigest()
 return {'schema':1,'request_id':uuid.uuid4().hex,'heads':heads,'engine_lock':lock,'adapter_version':1,
         'version_name':VERSION+'.'+time.strftime('%Y%m%d%H%M%S',time.gmtime()),'version_code':int(time.time()//60),
         'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'mode':mode}

def ensure_tools(state,job):
 emit('stage',fraction=.14,title='Preparando Android SDK, Java y Rust')
 sdk=bootstrap.ensure_sdk(state,job.get('accept_sdk_license',False));java=bootstrap.ensure_java(state)
 env,compiler=bootstrap.ensure_rust(state,'1.99.1')
 env.update(JAVA_HOME=str(java),PATH=str(java/'bin')+os.pathsep+env['PATH'],CARGO_BUILD_JOBS=str(job['jobs']),GIT_TERMINAL_PROMPT='0')
 os.environ.clear();os.environ.update(env)
 return sdk,java,compiler

def product_key(state,mode,name,job,java):
 slug='lucy' if mode=='lucy' else name
 args=SimpleNamespace(import_key=Path(job['import_key']) if job.get('import_key') else None,
                      import_password_env='LUCY_IMPORT_PASSWORD' if job.get('import_key') else None,key_alias=job.get('key_alias') or None)
 return legacy.ensure_identity(state/'identities'/slug,dict(os.environ),java,args)

def office(ids,state,output,job,tools):
 emit('stage',fraction=.05,title='Seleccionando las fuentes de '+', '.join(BY_ID[x].name for x in ids))
 if job.get('download_only'):
  heads={};paths=[]
  for name in ids:
   folder,commit=sources(name,state,job['revision_mode']);heads[name]=commit;paths.append(str(folder))
  emit('revisions',heads=heads);emit('sources',paths=paths);return None
 snapshot=resolve(ids,job['revision_mode'],job.get('language_mode','all'));save(state/'last-snapshot.json',snapshot)
 emit('revisions',heads=snapshot['heads'])
 prepared=legacy.prepare(snapshot,state)
 from . import proofing
 language_data=proofing.prepare(snapshot,prepared,state)
 sdk,java,compiler=tools() if callable(tools) else tools;snapshot['compiler']=compiler
 key,password=product_key(state,job['mode'],ids[0],job,java)
 legacy.shared_fonts(snapshot,prepared,state)
 emit('stage',fraction=.23,title='Compilando los editores seleccionados')
 artifacts=legacy.compile_all(snapshot,prepared,state,compiler,job['jobs'])
 proofing.add_notices(language_data,artifacts)
 emit('stage',fraction=.84,title='Empaquetando y verificando la APK')
 result=host.publish(snapshot,artifacts,state,output,sdk,key,password,job['mode'])
 emit('result',result=result);return result

def sources(app_id,state,revision_mode):
 app=BY_ID[app_id]
 commit=revision(app_id,revision_mode)
 folder=state/'sources'/app_id/commit
 if folder.exists():
  import subprocess
  if subprocess.check_output(['git','rev-parse','HEAD'],cwd=folder,text=True).strip()!=commit:raise ValueError('Fuente de otra revisión.')
  import hashlib
  if legacy.source_hash(folder)!=hashlib.sha256(b'').hexdigest():raise ValueError('La fuente fue modificada. Conservá esos cambios fuera de la caché antes de continuar.')
 else:pipeline.clone_commit(app.repository,commit,folder)
 return folder,commit

def run(job,state):
 mode=job.get('mode');ids=selection(mode,job.get('apps'))
 if job.get('revision_mode','main') not in MODES:raise ValueError('Origen de revisiones inválido.')
 job['revision_mode']=job.get('revision_mode','main');job['jobs']=int(job.get('jobs',legacy.default_jobs()))
 if not 1<=job['jobs']<=32:raise ValueError('Número de trabajos fuera de rango.')
 if mode=='individual' and not job.get('download_only') and any(BY_ID[name].recipe=='source' for name in ids):raise ValueError('Una de las aplicaciones seleccionadas solo permite descargar sus fuentes; no publica un destino Android compatible.')
 if job.get('language_mode','all') not in {'all','es'}:raise ValueError('Perfil de idiomas inválido.')
 bootstrap.host_check();state=state.expanduser().resolve();state.mkdir(parents=True,exist_ok=True);state.chmod(0o700)
 lock=(state/'build.lock').open('a+')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise ValueError('Ya hay otra compilación usando esta caché.')
 (state/'work').mkdir(exist_ok=True)
 output=Path(job['output']).expanduser().resolve();output.mkdir(parents=True,exist_ok=True)
 logs=state/'logs';logs.mkdir(exist_ok=True);log=logs/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.log')
 emit('started',log=str(log),apps=list(ids))
 old_env=dict(os.environ)
 try:
  with legacy.LogCapture(log):
   tools=None
   def get_tools():
    nonlocal tools
    if tools is None:tools=ensure_tools(state,job)
    return tools
   if mode=='lucy':office(ids,state,output,job,get_tools)
   else:
    for index,name in enumerate(ids):
     emit('application',name=BY_ID[name].name,index=index+1,total=len(ids))
     if name in OFFICE:office((name,),state,output,job,get_tools)
     elif job.get('download_only'):
      folder,commit=sources(name,state,job['revision_mode']);emit('revisions',heads={name:commit});emit('sources',paths=[str(folder)])
     elif BY_ID[name].recipe=='native':
      from .native_cad import build
      emit('result',result=build(state,output,job,get_tools()))
     else:
      from .web import build
      emit('result',result=build(name,state,output,job,get_tools()))
   emit('stage',fraction=1,title='Fuentes listas' if job.get('download_only') else 'Compilación terminada')
  emit('finished',success=True,log=str(log))
 finally:os.environ.clear();os.environ.update(old_env);lock.close()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--job',type=Path,required=True);parser.add_argument('--state',type=Path,required=True);args=parser.parse_args()
 try:
  job=json.loads(args.job.read_text());run(job,args.state)
 except KeyboardInterrupt:emit('cancelled');return 130
 except Exception as error:
  emit('failed',message=str(error));print(str(error),file=sys.stderr);return 1
 return 0
if __name__=='__main__':sys.exit(main())
