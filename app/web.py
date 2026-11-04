"""Source builds for the other Craft web targets, packaged locally for Android."""
from pathlib import Path
from html.parser import HTMLParser
import copy,importlib.util,json,os,re,shutil,subprocess,tempfile,tomllib,time
from .core import legacy,bootstrap,pipeline
from .catalog import BY_ID
from . import host

class TrunkLinks(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='link':self.links.append(dict(attrs))

def checked_path(base,value):
 result=(base/value).resolve()
 if not result.is_relative_to(base.resolve()):raise ValueError('Recurso fuera de la fuente: '+str(value))
 return result

def build_trunk(source,name,target,bindgen,env):
 page=source/'apps'/str(name+'-web')/'index.html';html=page.read_text();parser=TrunkLinks();parser.feed(html)
 rust=[row for row in parser.links if row.get('rel')=='rust']
 if len(rust)!=1:raise ValueError('Se esperaba una entrada Rust en '+str(page))
 recipe=rust[0];profile=recipe.get('data-cargo-profile','release');binary=recipe.get('data-bin',name+'-web')
 if not re.fullmatch('[a-zA-Z0-9_-]+',profile) or not re.fullmatch('[a-zA-Z0-9_-]+',binary):raise ValueError('Perfil web inválido.')
 command=['cargo','build','--locked','--target','wasm32-unknown-unknown','--profile',profile,'--manifest-path',str(page.parent/'Cargo.toml'),'--bin',binary]
 if recipe.get('data-cargo-features'):command.extend(['--features',recipe['data-cargo-features']])
 if 'data-cargo-no-default-features' in recipe:command.append('--no-default-features')
 subprocess.run(command,cwd=source,env=env,check=True)
 dist=source/'dist/lucy-android';shutil.rmtree(dist,ignore_errors=True);dist.mkdir(parents=True)
 raw=target/'wasm32-unknown-unknown'/profile/(binary+'.wasm')
 subprocess.run([bindgen,'--target','web','--no-typescript','--weak-refs','--out-dir',str(dist),'--out-name',binary,str(raw)],env=env,check=True)
 script=f'''<script type="module">import init,* as bindings from './{binary}.js';const wasm=await init({{module_or_path:'./{binary}_bg.wasm'}});window.wasmBindings=bindings;dispatchEvent(new CustomEvent('TrunkApplicationStarted',{{detail:{{wasm}}}}));</script>'''
 html,count=re.subn(r'<link\b[^>]*\brel=[\'"]rust[\'"][^>]*>',lambda _:script,html)
 if count!=1:raise ValueError('No se pudo enlazar el programa web.')
 for row in parser.links:
  rel=row.get('rel');href=row.get('href')
  if rel not in {'copy-file','copy-dir','css','stylesheet'} or not href or href.startswith(('http:','https:')):continue
  origin=(page.parent/href).resolve()
  if not origin.is_relative_to(source.resolve()):raise ValueError('Recurso externo no permitido.')
  dest=checked_path(dist,Path(row.get('data-target-path',''))/origin.name)
  dest.parent.mkdir(parents=True,exist_ok=True)
  if origin.is_dir():shutil.copytree(origin,dest,dirs_exist_ok=True)
  else:shutil.copy2(origin,dest)
  html=html.replace(href,dest.relative_to(dist).as_posix())
 html=re.sub(r'<link\b[^>]*\brel=[\'"]icon[\'"][^>]*>','',html)
 (dist/'index.html').write_text(html);return dist

def recipe(name):
 return 'xtask' if name in {'filmcraft','effectcraft','lightcraft'} else 'trunk'

def export_engine(source,dist,output,name,commit,snapshot):
 engine=output/'engine';engine.mkdir(parents=True)
 for item in sorted(dist.rglob('*')):
  if not item.is_file() or item.is_symlink() or item.suffix in {'.gz','.br','.map'}:continue
  rel=item.relative_to(dist);dest=engine/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,dest)
 index=engine/'index.html';text=index.read_text()
 signal='''<script>(()=>{let ready=false;const painted=gl=>{if(ready||!gl.canvas?.isConnected||!gl.canvas.id)return;ready=true;requestAnimationFrame(()=>requestAnimationFrame(()=>dispatchEvent(new Event('LucyFirstPaint'))));};for(const type of [window.WebGLRenderingContext,window.WebGL2RenderingContext])if(type)for(const name of ['drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced']){const old=type.prototype[name];if(old)type.prototype[name]=function(...args){const result=old.apply(this,args);painted(this);return result;};}})();</script>'''
 text=re.sub(r'<head\b[^>]*>',lambda m:m[0]+'<script src="../../engine-adapter.js"></script>'+signal,text,count=1)
 index.write_text(text)
 if not any(p.suffix=='.wasm' for p in engine.rglob('*')):raise ValueError('El empaquetado web no contiene el motor compilado.')
 (output/'adapter.patch').write_bytes(b'')
 entry={'id':name,'label':BY_ID[name].name,'repository':BY_ID[name].repository,'version':tomllib.loads((source/'Cargo.toml').read_text())['workspace']['package']['version'],'source_commit':commit,'source_branch':'main','source_prune':[],'recipe':'upstream-'+recipe(name)}
 pipeline.json_file(output/'engine.json',entry)
 files={p.relative_to(engine).as_posix():bootstrap.digest(p) for p in engine.rglob('*') if p.is_file()}
 pipeline.json_file(engine/'folio-engine.json',{'source_commit':commit,'folio_version':snapshot['version_name'],'files':files,'recipe':entry['recipe']})
 pipeline.copy_notice_tree(source,output/'notices'/name)
 pipeline.cargo_notices(source,name,output/'notices',dict(os.environ))
 return entry

def build(name,state,output,job,tools):
 from .worker import emit,sources,product_key
 sdk,java,compiler=tools
 emit('stage',fraction=.05,title='Descargando '+BY_ID[name].name)
 source,commit=sources(name,state,job['revision_mode']);emit('revisions',heads={name:commit})
 base=json.loads((pipeline.TEMPLATE/'engine-lock.json').read_text());lock=copy.deepcopy(base)
 lock['translations']={'mode':'embedded-in-upstream','repository':BY_ID[name].repository,'source_commit':commit}
 font_rev=(source/'craft-fonts.rev').read_text().strip() if (source/'craft-fonts.rev').exists() else (json.loads((Path(__file__).parents[1]/'app/verified.json').read_text())['fonts']['source_commit'] if job['revision_mode']=='verified' else pipeline.latest('storytold/craft-fonts'))
 if not pipeline.SHA.fullmatch(font_rev):raise ValueError('Revisión de fuentes inválida.')
 fonts=state/'cache/fonts'/font_rev
 if not fonts.exists():pipeline.clone_commit('storytold/craft-fonts',font_rev,fonts)
 lock['fonts']['source_commit']=font_rev
 env=dict(os.environ);env.update(CRAFT_FONTS_DIR=str(fonts),CRAFT_FONTS_REQUIRED='1',CARGO_TARGET_DIR=str(state/'cache/cargo-target'))
 rev_file=source/'craft-i18n.rev';translations=None
 if rev_file.exists():
  rev=rev_file.read_text().strip()
  if not pipeline.SHA.fullmatch(rev):raise ValueError('Revisión de traducción inválida.')
  translations=state/'cache/catalogs'/rev
  if not translations.exists():pipeline.clone_commit('storytold/craft-i18n',rev,translations)
  env.update(CRAFT_I18N_DIR=str(translations),CRAFT_I18N_REQUIRED='1');lock['translations']={'repository':'storytold/craft-i18n','source_commit':rev}
 snapshot={'heads':{name:commit},'engine_lock':lock,'compiler':compiler,'version_name':'2.0.'+time.strftime('%Y%m%d%H%M%S',time.gmtime()),'version_code':int(time.time()//60),'adapter_version':2,'mode':job['revision_mode']}
 cache_key=legacy.key_of({'name':name,'commit':commit,'compiler':compiler,'recipe':bootstrap.digest(Path(__file__)),'fonts':font_rev,'translations':lock['translations']['source_commit']})
 cache=state/'cache/web-engines'/name/cache_key
 if not legacy.cache_valid(cache,cache_key,commit):
  work=state/'work/web'/name
  if not work.exists():pipeline.copy_template(work)
  spec=importlib.util.spec_from_file_location('web_build_tools',work/'scripts/build_engines.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  cargo=tomllib.loads((source/'Cargo.lock').read_text());version=next(p['version'] for p in cargo['package'] if p['name']=='wasm-bindgen');bindgen=module.tool('wasm-bindgen',version)
  env['PATH']=str(Path(bindgen).parent)+os.pathsep+env['PATH']
  emit('stage',fraction=.23,title='Compilando '+BY_ID[name].name)
  target=Path(env['CARGO_TARGET_DIR'])
  if recipe(name)=='xtask':
   subprocess.run(['cargo','xtask','web'],cwd=source,env=env,check=True)
   dist=target/('web-site' if name=='lightcraft' else 'web/dist')
  else:dist=build_trunk(source,name,target,bindgen,env)
  if not (dist/'index.html').is_file():raise ValueError('La compilación no generó la aplicación web.')
  with tempfile.TemporaryDirectory(prefix='web-result-',dir=state/'work') as tmp:
   result=Path(tmp)/'output';result.mkdir();entry=export_engine(source,dist,result,name,commit,snapshot)
   pipeline.copy_notice_tree(fonts,result/'notices/craft-fonts')
   if translations is not None:pipeline.copy_notice_tree(translations,result/'notices/craft-i18n')
   staging=cache.with_name(cache.name+'.tmp-'+str(os.getpid()));staging.parent.mkdir(parents=True,exist_ok=True);shutil.rmtree(staging,ignore_errors=True);shutil.copytree(result,staging)
   legacy.save_json(staging/'cache.json',{'cache_key':cache_key,'commit':commit,'files':{p.relative_to(staging).as_posix():bootstrap.digest(p) for p in staging.rglob('*') if p.is_file()}})
   if cache.exists():shutil.rmtree(cache)
   os.replace(staging,cache)
 else:emit('stage',fraction=.75,title='Reutilizando '+BY_ID[name].name+' verificado')
 entry=json.loads((cache/'engine.json').read_text());snapshot['engine_lock']['engines']=[entry]
 artifacts=state/'work/web-artifacts';artifacts.mkdir(exist_ok=True)
 destination=artifacts/name;shutil.rmtree(destination,ignore_errors=True);shutil.copytree(cache,destination,ignore=shutil.ignore_patterns('cache.json'))
 manifest=json.loads((destination/'engine/folio-engine.json').read_text());manifest['folio_version']=snapshot['version_name'];legacy.save_json(destination/'engine/folio-engine.json',manifest)
 key,password=product_key(state,'individual',name,job,java)
 emit('stage',fraction=.85,title='Creando APK de '+BY_ID[name].name)
 return host.publish(snapshot,artifacts,state,output,sdk,key,password,'individual')
