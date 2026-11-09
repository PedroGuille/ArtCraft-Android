"""Build a real Android host containing exactly the selected engines."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import json,os,re,shutil,time,uuid,tempfile
import xml.etree.ElementTree as ET
from .core import legacy,bootstrap,pipeline
from .catalog import BY_ID,OFFICE,selection

NS='{http://schemas.android.com/apk/res/android}'
MIME={
 'wordcraft':['application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/msword','application/vnd.oasis.opendocument.text','text/plain','text/rtf'],
 'pdfcraft':['application/pdf'],
 'gridcraft':['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/vnd.ms-excel','text/csv','text/tab-separated-values'],
 'deckcraft':['application/vnd.openxmlformats-officedocument.presentationml.presentation'],
}
OFFICE_META={
 'wordcraft':dict(label='Documentos',name='Documento.docx',template='blank.docx'),
 'gridcraft':dict(label='Hojas de cálculo',name='Libro.xlsx',template='blank.xlsx'),
 'deckcraft':dict(label='Presentaciones',name='Presentación.pptx'),
 'pdfcraft':dict(label='PDF',name='Documento.pdf',template='blank.pdf'),
}

def identity(mode,ids):
 ids=selection(mode,list(ids))
 if mode=='lucy':return 'Lucy','io.github.pedroguille.folio','lucy'
 if len(ids)!=1:raise ValueError('Una APK independiente contiene una aplicación.')
 app=BY_ID[ids[0]]
 return app.name,'io.github.pedroguille.'+app.id.replace('-',''),app.id

def configure(project,mode,ids):
 ids=selection(mode,list(ids));title,package,slug=identity(mode,ids)
 assets=project/'app/src/main/assets';meta={}
 for name in ids:
  app=BY_ID[name];row=dict(OFFICE_META.get(name,dict(label=app.name,name='Nuevo.'+app.extensions[0])))
  row['exts']=list(app.extensions)
  if name not in OFFICE:row['query']='webgl&empty&nosw'
  meta[name]=row
 js=assets/'shell.js';text=js.read_text()
 text,count=re.subn(r'  const engines = \{.*?\n  \};','  const engines = '+json.dumps(meta,ensure_ascii=False)+';',text,count=1,flags=re.S)
 if count!=1:raise ValueError('No se encontró el catálogo del host Android.')
 text=text.replace('${{wordcraft:"W",gridcraft:"X",deckcraft:"P",pdfcraft:"PDF"}[id]}','${({wordcraft:"W",gridcraft:"X",deckcraft:"P",pdfcraft:"PDF"}[id] || engines[id].label.slice(0,2))}')
 text=text.replace('`engines/${id}/index.html?webgl&blank`','`engines/${id}/index.html?${engine.query || "webgl&blank"}`')
 if mode=='individual':
  text=text.replace('return Object.keys(engines).find(key => engines[key].exts.includes(ext));','return Object.keys(engines).find(key => engines[key].exts.includes(ext)) || Object.keys(engines)[0];')
 text=text.replace('Salir de Lucy','Salir de '+title);js.write_text(text)
 html=assets/'index.html';text=html.read_text().replace('<title>Lucy</title>','<title>'+title+'</title>')
 def button(match):return match[0] if match[1] in ids else ''
 text=re.sub(r'<button\b[^>]*\bdata-new="([^"]+)"[^>]*>.*?</button>',button,text,flags=re.S)
 for name in ids:
  if name not in OFFICE:
   item='<button data-new="'+name+'"><span class="tab-icon">'+BY_ID[name].name[:2]+'</span><span>Nuevo proyecto</span></button>'
   text=text.replace('<div class="create-options">','<div class="create-options">'+item)
   text=text.replace('<button id="show-recoveries"',item+'<button id="show-recoveries"')
 html.write_text(text)
 if not any(name in OFFICE for name in ids):
  adapter=assets/'engine-adapter.js';adapter.write_text(adapter.read_text().replace('window.addEventListener("TrunkApplicationStarted",watchReady,{once:true});','window.addEventListener("LucyFirstPaint",watchReady,{once:true});'))
 (assets/'selection.json').write_text(json.dumps({'mode':mode,'engines':list(ids),'name':title,'package':package}))
 manifest=project/'app/src/main/AndroidManifest.xml';ET.register_namespace('android',NS[1:-1]);tree=ET.parse(manifest);r=tree.getroot()
 r.set('package',package)
 for provider in r.findall('application/provider'):provider.set(NS+'authorities',package+'.recovery')
 types=sorted({m for app in ids for m in MIME.get(app,['application/octet-stream'])})
 for intent in r.findall('application/activity/intent-filter'):
  actions=[x.get(NS+'name') for x in intent.findall('action')]
  if 'android.intent.action.MAIN' in actions:continue
  for element in list(intent.findall('data')):intent.remove(element)
  for mime in types:
   data=ET.SubElement(intent,'data');data.set(NS+'mimeType',mime)
   if 'android.intent.action.VIEW' in actions:data.set(NS+'scheme','content')
 tree.write(manifest,encoding='utf-8',xml_declaration=True)
 if package!='io.github.pedroguille.folio':
  for source in (project/'app/src/main/java').rglob('*.java'):
   source.write_text(source.read_text().replace('io.github.pedroguille.folio',package))
 strings=project/'app/src/main/res/values/strings.xml';tree=ET.parse(strings)
 for element in tree.getroot():
  if element.get('name')=='app_name':element.text=title
 tree.write(strings,encoding='utf-8',xml_declaration=True)
 if mode=='individual' and (ROOT_ICON:=Path(__file__).parent/'icons'/str(ids[0]+'.png')).is_file():
  icon_dir=project/'app/src/main/res/drawable-nodpi';(icon_dir/'lucy_icon.jpg').unlink(missing_ok=True);shutil.copyfile(ROOT_ICON,icon_dir/'lucy_icon.png')
 if not any(name in OFFICE for name in ids):
  storage=next((project/'app/src/main/java').rglob('Storage.java'));java=storage.read_text()
  extra={'.svg':'image/svg+xml','.webp':'image/webp','.otf':'font/otf','.woff2':'font/woff2','.wav':'audio/wav','.mp3':'audio/mpeg','.flac':'audio/flac','.ogg':'audio/ogg','.mp4':'video/mp4','.webm':'video/webm','.mov':'video/quicktime'}
  java=java.replace('        return "application/octet-stream";',''.join('        if (n.endsWith('+json.dumps(ext)+')) return '+json.dumps(mime)+';\n' for ext,mime in extra.items())+'        return "application/octet-stream";',1);storage.write_text(java)
 templates={meta[name].get('template') for name in ids}-{None}
 script=project/'scripts/create_templates.py'
 script.write_text(script.read_text()+'\n# Only selected document templates enter this APK.\nfor path in OUT.iterdir():\n    if path.is_file() and path.name not in '+repr(templates)+': path.unlink()\n')
 return title,package,slug

def verify_assets(project,snapshot):
 root=project/'app/src/main/assets/engines';expected=set(snapshot['heads'])
 if {p.name for p in root.iterdir() if p.is_dir()}!=expected:raise ValueError('La APK contiene una selección de motores incorrecta.')
 for name in expected:
  folder=root/name;data=json.loads((folder/'folio-engine.json').read_text())
  if data.get('source_commit')!=snapshot['heads'][name]:raise ValueError('Motor de otra revisión: '+name)
  for rel,digest in data['files'].items():
   path=folder/rel
   if not path.resolve().is_relative_to(folder.resolve()) or bootstrap.digest(path)!=digest:raise ValueError('Recurso modificado: '+name+'/'+rel)
  if not any(n.endswith('.wasm') for n in data['files']):raise ValueError('Falta WebAssembly: '+name)

def archive_sources(project,destination):
 # Flatpak files have an epoch mtime; ZIP can represent only 1980–2107.
 # Clamp archive metadata without changing the files or compiler cache.
 with ZipFile(destination,'w',ZIP_DEFLATED,compresslevel=6,strict_timestamps=False) as z:
  for folder,dirs,files in os.walk(project):
   dirs[:]=sorted(d for d in dirs if d not in {'build','.cache','.git','__pycache__','engines'})
   for file in sorted(files):
    p=Path(folder)/file
    if p.suffix not in {'.p12','.pfx','.jks','.keystore','.apk','.pyc'}:z.write(p,'source/'+p.relative_to(project).as_posix())

def assemble(snapshot,artifacts,work,sdk,mode):
 project=work/'project';pipeline.copy_template(project);lock=snapshot['engine_lock']
 for index,engine in enumerate(lock['engines']):
  name=engine['id'];folder=artifacts/name;actual=json.loads((folder/'engine.json').read_text())
  if actual['source_commit']!=snapshot['heads'][name]:raise ValueError('Artefacto incorrecto: '+name)
  lock['engines'][index]=actual
  shutil.copytree(folder/'engine',project/'app/src/main/assets/engines'/name)
  shutil.copyfile(folder/'adapter.patch',project/'third_party/patches'/str(name+'.patch'))
  shutil.copytree(folder/'notices',project/'third_party',dirs_exist_ok=True)
 pipeline.json_file(project/'engine-lock.json',lock)
 title,package,slug=configure(project,mode,list(snapshot['heads']))
 verify_assets(project,snapshot)
 for name in list((project/'third_party/patches').glob('*.patch')):
  if name.stem not in snapshot['heads']:name.unlink()
 for name in OFFICE:
  if name not in snapshot['heads']:shutil.rmtree(project/'third_party'/name,ignore_errors=True)
 manifest=project/'app/src/main/AndroidManifest.xml';tree=ET.parse(manifest);tree.getroot().set(NS+'versionName',snapshot['version_name']);tree.getroot().set(NS+'versionCode',str(snapshot['version_code']));tree.write(manifest,encoding='utf-8',xml_declaration=True)
 info={'schema':2,'builder':'Lucy Builder 2.3.0','name':title,'package_name':package,'mode':mode,'source_selection':snapshot.get('mode','main'),'language_mode':snapshot['engine_lock'].get('language_mode','upstream'),'selection':list(snapshot['heads']),
       'version_name':snapshot['version_name'],'version_code':snapshot['version_code'],'heads':snapshot['heads'],'engines':lock['engines'],
       'compiler':snapshot['compiler'],'fonts':lock['fonts'],'translations':lock['translations'],'built_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 pipeline.json_file(project/'third_party/SOURCES.json',info)
 notices=['Lucy Builder: aplicación Android compilada desde sus fuentes.\n']
 for path in sorted((project/'third_party').rglob('*')):
  if path.is_file() and 'patches' not in path.parts and 'spanish' not in path.parts:
   notices.extend(['\n'+path.relative_to(project).as_posix()+'\n',path.read_bytes().decode('utf-8',errors='replace')])
 (project/'app/src/main/assets/THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices))
 apk=pipeline.package_unsigned(project,sdk);result=work/'result';result.mkdir();shutil.copyfile(apk,result/'unsigned.apk')
 archive_sources(project,result/'source.zip')
 return result,info,slug

def publish(snapshot,artifacts,state,output,sdk,key,password,mode):
 with tempfile.TemporaryDirectory(prefix='package-',dir=state/'work') as tmp:
  result,info,slug=assemble(snapshot,artifacts,Path(tmp),sdk,mode)
  signed=result/(info['name']+'.apk');certificate=legacy.sign_apk(sdk,key,password,result/'unsigned.apk',signed)
  info.update(signed=True,apk_sha256=bootstrap.digest(signed),certificate_sha256=certificate)
  output=output.expanduser().resolve();product=output/slug
  if product.is_symlink():raise ValueError('La salida de la aplicación no puede ser un enlace.')
  marker=product/'.lucy-output.json'
  if marker.exists() and legacy.read_json(marker,{}).get('format')!='lucy-gui-output-2':raise ValueError('La carpeta no pertenece a este constructor: '+str(product))
  if product.exists() and not marker.exists() and any(product.iterdir()):raise ValueError('La carpeta de salida contiene otros archivos: '+str(product))
  product.mkdir(parents=True,exist_ok=True);legacy.save_json(marker,{'format':'lucy-gui-output-2'})
  with tempfile.TemporaryDirectory(prefix='.publish-',dir=product) as staging:
   stage=Path(staging);name=info['name'];shutil.copy2(signed,stage/(name+'.apk'));shutil.copy2(result/'source.zip',stage/(name+'-source.zip'));legacy.save_json(stage/'build-info.json',info)
   final=product/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);os.replace(stage,final)
  return {**info,'apk':str(final/(name+'.apk')),'source':str(final/(name+'-source.zip')),'report':str(final/'build-info.json'),'output':str(final)}
