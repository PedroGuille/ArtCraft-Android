#!/usr/bin/env python3
"""Descargar main de los cuatro editores y compilar Lucy en Linux, sin cuentas."""
from __future__ import annotations
import argparse,concurrent.futures,copy,fcntl,getpass,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,tempfile,time,uuid,threading
from pathlib import Path
from zipfile import ZipFile
import bootstrap as tools

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('lucy_pipeline',ROOT/'pipeline/build_lucy.py')
pipeline=importlib.util.module_from_spec(spec);spec.loader.exec_module(pipeline)
VERSION='1.0.0'

class BuildFailure(Exception):pass

def read_json(path,default=None):
    try:return json.loads(Path(path).read_text())
    except FileNotFoundError:return default

def save_json(path,data):tools.atomic(Path(path),(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())
def key_of(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run(argv,env=None,capture=False):
    return subprocess.run(list(map(str,argv)),env=env,check=True,stdout=subprocess.PIPE if capture else None,stderr=subprocess.STDOUT if capture else None,text=capture).stdout

def repeat_snapshot(base,previous,request_id):
    if not previous or previous.get('schema')!=1:raise BuildFailure('No hay una selección anterior para repetir. Ejecutá primero sin --repeat.')
    heads=pipeline.validate_heads(previous['heads']);lock=copy.deepcopy(base)
    for engine in lock['engines']:
        engine['adapter_base_commit']=engine['source_commit'];engine['source_commit']=heads[engine['id']];engine['source_branch']='main';engine.pop('source_date',None)
    for name in ['fonts','translations']:
        prior=previous['engine_lock'][name];commit=prior.get('source_commit','')
        if not pipeline.SHA.fullmatch(commit):raise BuildFailure('La selección anterior contiene una revisión inválida.')
        lock[name]['source_commit']=commit
    files=previous['engine_lock']['translations']['files']
    if set(files)!=set(lock['translations']['files']) or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in files.values()):raise BuildFailure('Los catálogos anteriores no son los dos catálogos españoles esperados.')
    lock['translations']['files']=copy.deepcopy(files)
    return {'schema':1,'request_id':request_id,'heads':heads,'engine_lock':lock,'adapter_version':1,'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}

def default_jobs():
    total=os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
    try:
        limited=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if limited.isdigit():total=min(total,int(limited))
    except OSError:pass
    return max(1,min(4,os.cpu_count() or 1,total//(3*1024**3)))

def output_root(path):
    path=path.expanduser().resolve()
    if path.exists() and not (path/'.lucy-output.json').is_file() and any(path.iterdir()):
        raise BuildFailure('La carpeta de salida ya contiene otros archivos. Elegí una vacía con --output.')
    path.mkdir(parents=True,exist_ok=True)
    marker=read_json(path/'.lucy-output.json')
    if marker and marker.get('format')!='lucy-linux-output-1':raise BuildFailure('Carpeta de salida no reconocida.')
    save_json(path/'.lucy-output.json',{'format':'lucy-linux-output-1'})
    builds=path/'builds'
    if builds.is_symlink() or (builds.exists() and not builds.is_dir()):raise BuildFailure('La carpeta builds de salida no puede ser un enlace ni un archivo.')
    for name in ['latest','Lucy.apk','Lucy-source.zip','build-info.json','build.log']:
        item=path/name
        if item.is_symlink():
            target=item.resolve()
            if not target.is_relative_to(path):raise BuildFailure('La salida contiene un enlace externo: '+str(item))
            if name!='latest' and item.readlink()!=Path('latest')/name:raise BuildFailure('La salida contiene un enlace modificado. Elegí otra carpeta con --output: '+str(item))
        elif item.exists():raise BuildFailure('Se conserva un archivo que no pertenece al constructor: '+str(item))
    return path

def source_hash(source):
    data=subprocess.check_output(['git','diff','--binary','HEAD'],cwd=source)
    extras=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=source)
    if extras:raise BuildFailure('Hay archivos nuevos en la fuente de caché. Guardalos fuera de ella antes de continuar: '+str(source))
    return hashlib.sha256(data).hexdigest()

def prepare(snapshot,state):
    prepared={};profile=pipeline.TEMPLATE
    for engine in snapshot['engine_lock']['engines']:
        name=engine['id'];work=state/'work/engines'/name;record=work/'.lucy-owned.json'
        source=work/'sources'/name
        plan_key=key_of({'engine':engine,'fonts':snapshot['engine_lock']['fonts'],'translations':snapshot['engine_lock']['translations'],
                         'patch':tools.digest(profile/'third_party/patches'/str(name+'.patch')),'pipeline':tools.digest(ROOT/'pipeline/build_lucy.py'),
                         'builder':tools.digest(profile/'scripts/build_engines.py')})
        prior=read_json(record)
        if work.is_symlink():raise BuildFailure('La carpeta de trabajo no puede ser un enlace.')
        if work.exists():
            if not prior or prior.get('engine')!=name:raise BuildFailure('Se conserva una carpeta de trabajo no reconocida: '+str(work))
            if prior.get('source_hash') and source.is_dir():
                if source_hash(source)!=prior['source_hash']:raise BuildFailure('La fuente de trabajo fue modificada fuera del constructor. Guardá esos cambios antes de continuar: '+str(source))
            if prior.get('plan_key')==plan_key and source.is_dir() and prior.get('source_hash'):
                engine.update(prior['prepared_engine']);prepared[name]=work
                print(name+': fuente preparada, sin cambios.',flush=True);continue
            shutil.rmtree(work)
        work.mkdir(parents=True);save_json(record,{'engine':name,'plan_key':plan_key,'status':'preparing'})
        print('Descargando e integrando '+name+' · '+engine['source_commit'][:10]+'…',flush=True)
        pipeline.prepare_engine(snapshot,name,work)
        save_json(record,{'engine':name,'plan_key':plan_key,'source_hash':source_hash(source),'prepared_engine':copy.deepcopy(engine),'status':'ready'})
        prepared[name]=work
    return prepared

def export_identity(env,keytool,source,password,alias,destination,dest_password):
    temporary=destination.with_name(destination.name+'.part.p12')
    temporary.unlink(missing_ok=True)
    scope={**env,'LUCY_IMPORT_PASSWORD':password,'LUCY_DEST_PASSWORD':dest_password}
    listing=run([keytool,'-J-Duser.language=en','-J-Duser.country=US','-list','-rfc','-keystore',source,'-storepass:env','LUCY_IMPORT_PASSWORD'],scope,True)
    entries=[]
    for part in listing.split('Alias name: ')[1:]:
        if 'Entry type: PrivateKeyEntry' in part:entries.append(part.splitlines()[0].strip())
    if alias:
        if alias not in entries:raise BuildFailure('No se encontró esa clave privada en la firma importada.')
    elif len(entries)==1:alias=entries[0]
    else:raise BuildFailure('La copia no contiene una única clave privada. Indicá --key-alias.')
    try:
        run([keytool,'-J-Duser.language=en','-importkeystore','-srckeystore',source,'-srcstorepass:env','LUCY_IMPORT_PASSWORD','-srckeypass:env','LUCY_IMPORT_PASSWORD',
             '-srcalias',alias,'-destkeystore',temporary,'-deststoretype','PKCS12','-destalias','lucy','-deststorepass:env','LUCY_DEST_PASSWORD','-destkeypass:env','LUCY_DEST_PASSWORD','-noprompt'],scope,True)
        temporary.chmod(0o600);os.replace(temporary,destination)
    finally:temporary.unlink(missing_ok=True)

def key_input(path,folder):
    path=path.expanduser().resolve()
    if path.stat().st_size>8*1024*1024:raise BuildFailure('La copia de firma es demasiado grande.')
    import zipfile
    if not zipfile.is_zipfile(path):return path
    with ZipFile(path) as z:
        entries=z.infolist()
        if len(entries)>32 or sum(e.file_size for e in entries)>8*1024*1024:raise BuildFailure('La copia ZIP de firma supera el límite.')
        keys=[e for e in entries if not e.is_dir() and Path(e.filename).suffix.lower() in {'.jks','.keystore','.p12','.pfx'}]
        if len(keys)!=1:raise BuildFailure('La copia ZIP debe contener una única firma JKS o PKCS12.')
        with z.open(keys[0]) as src:data=src.read(8*1024*1024+1)
        if len(data)>8*1024*1024:raise BuildFailure('La firma descomprimida supera el límite.')
        out=folder/'imported-key';tools.atomic(out,data);return out

def ensure_identity(state,env,java_home,args):
    folder=state/'signing';folder.mkdir(parents=True,exist_ok=True);folder.chmod(0o700)
    current=folder/'current';identities=folder/'identities';identities.mkdir(exist_ok=True)
    if current.exists() or current.is_symlink():
        if not current.is_symlink() or not current.resolve().is_relative_to(identities.resolve()):raise BuildFailure('El directorio de firma no pertenece al constructor.')
    keytool=java_home/'bin/keytool'
    if args.import_key or not current.exists():
        candidate=identities/uuid.uuid4().hex;candidate.mkdir(mode=0o700)
        password=os.urandom(32).hex()
        try:
            if args.import_key:
                if args.import_password_env:
                    source_password=os.environ.get(args.import_password_env)
                    if source_password is None:raise BuildFailure('No está definida la variable de contraseña indicada.')
                elif sys.stdin.isatty():source_password=getpass.getpass('Contraseña de la firma anterior (Enter: android): ') or 'android'
                else:raise BuildFailure('La importación necesita un terminal o --import-password-env.')
                with tempfile.TemporaryDirectory(prefix='import-',dir=folder) as tmp:
                    source=key_input(args.import_key,Path(tmp))
                    export_identity(env,keytool,source,source_password,args.key_alias,candidate/'lucy.p12',password)
            else:
                scope={**env,'LUCY_SIGN_PASSWORD':password}
                run([keytool,'-genkeypair','-keystore',candidate/'lucy.p12','-storetype','PKCS12','-alias','lucy','-storepass:env','LUCY_SIGN_PASSWORD','-keypass:env','LUCY_SIGN_PASSWORD',
                     '-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Lucy Personal Linux Build','-noprompt'],scope,True)
            (candidate/'lucy.p12').chmod(0o600);tools.atomic(candidate/'password.txt',password.encode())
            pointer=folder/('.current-'+uuid.uuid4().hex);pointer.symlink_to(Path('identities')/candidate.name,target_is_directory=True);os.replace(pointer,current)
            print('Firma anterior importada y comprobada.' if args.import_key else 'Firma personal creada; se reutilizará en las siguientes APK.',flush=True)
        except BaseException:
            shutil.rmtree(candidate,ignore_errors=True);raise
    key=current/'lucy.p12';password_file=current/'password.txt'
    if not key.is_file() or not password_file.is_file():raise BuildFailure('La firma guardada está incompleta; importá su copia antes de continuar.')
    scope={**env,'LUCY_SIGN_PASSWORD':password_file.read_text()}
    run([keytool,'-list','-keystore',key,'-storepass:env','LUCY_SIGN_PASSWORD','-alias','lucy'],scope,True)
    return key,password_file


def cache_valid(folder,cache_key,commit):
    meta=read_json(folder/'cache.json')
    if not meta or meta.get('cache_key')!=cache_key or meta.get('commit')!=commit:return False
    for name,sha in meta.get('files',{}).items():
        relative=Path(name);p=folder/relative
        if relative.is_absolute() or '..' in relative.parts or not p.resolve().is_relative_to(folder.resolve()) or not p.is_file() or tools.digest(p)!=sha:return False
    return bool(meta.get('files'))

def compile_all(snapshot,prepared,state,compiler,jobs):
    artifacts=state/'work/artifacts';artifacts.mkdir(parents=True,exist_ok=True)
    profile=pipeline.TEMPLATE
    for engine in snapshot['engine_lock']['engines']:
        name=engine['id'];work=prepared[name]
        inputs={'engine':engine,'fonts':snapshot['engine_lock']['fonts'],'translations':snapshot['engine_lock']['translations'],
                'ui_fonts':snapshot['engine_lock']['ui_fonts'],'compiler':compiler,'profile':tools.digest(profile/'third_party/patches'/str(name+'.patch')),
                'builder':tools.digest(profile/'scripts/build_engines.py'),'pipeline':tools.digest(ROOT/'pipeline/build_lucy.py')}
        cache_key=key_of(inputs);cache=state/'cache/engines'/name/cache_key
        if cache_valid(cache,cache_key,engine['source_commit']):
            print(name+': reutilizando el motor compilado y verificado.',flush=True)
        else:
            print('Compilando '+name+' con '+str(jobs)+' trabajos…',flush=True)
            # Keep the source and Cargo paths stable, but give each attempt a
            # new result directory. Interrupted output is never mixed into it.
            with tempfile.TemporaryDirectory(prefix='compile-'+name+'-',dir=state/'work') as temp:
                attempt=Path(temp)
                (attempt/'lucy').symlink_to(work/'lucy',target_is_directory=True)
                (attempt/'sources').symlink_to(work/'sources',target_is_directory=True)
                output=pipeline.compile_prepared(snapshot,name,attempt,state/'cache/cargo-target')
                staging=cache.with_name(cache.name+'.tmp-'+uuid.uuid4().hex)
                staging.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(output,staging)
                files={p.relative_to(staging).as_posix():tools.digest(p) for p in staging.rglob('*') if p.is_file()}
                save_json(staging/'cache.json',{'cache_key':cache_key,'commit':engine['source_commit'],'files':files})
                if cache.exists():shutil.rmtree(cache)
                os.replace(staging,cache)
        destination=artifacts/name
        if destination.exists():shutil.rmtree(destination)
        shutil.copytree(cache,destination,ignore=shutil.ignore_patterns('cache.json'))
        manifest=read_json(destination/'engine/folio-engine.json');manifest['folio_version']=snapshot['version_name'];save_json(destination/'engine/folio-engine.json',manifest)
    return artifacts

def shared_fonts(snapshot,prepared,state):
    commit=snapshot['engine_lock']['fonts']['source_commit'];fonts=state/'cache/fonts'/commit
    if not (fonts/'.git').exists():
        if fonts.exists():raise BuildFailure('Carpeta de fuentes incompleta. Conservada para revisión: '+str(fonts))
        pipeline.clone_commit('storytold/craft-fonts',commit,fonts)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=fonts,text=True).strip()
    if actual!=commit:raise BuildFailure('La caché tipográfica no corresponde a su revisión.')
    for work in prepared.values():
        target=work/'sources/craft-fonts'
        if target.is_symlink():
            if target.resolve()!=fonts.resolve():target.unlink()
        elif target.exists():raise BuildFailure('Carpeta de fuentes no reconocida en '+str(target))
        if not target.exists():target.symlink_to(fonts,target_is_directory=True)

def sign_apk(sdk,key,password,unsigned,signed):
    bt=sdk/'build-tools/36.0.0'
    # Our PKCS12 identities always use one password for the store and key.
    # apksigner shares a line reader for identical password-file arguments;
    # specifying that file twice consumes its only line on the second read.
    run([bt/'apksigner','sign','--ks',key,'--ks-type','PKCS12','--ks-key-alias','lucy','--ks-pass','file:'+str(password),'--out',signed,unsigned])
    verified=run([bt/'apksigner','verify','--verbose','--print-certs',signed],capture=True)
    if 'v2 scheme (APK Signature Scheme v2): true' not in verified:raise BuildFailure('La firma v2 no se verificó.')
    run([bt/'zipalign','-c','4',signed])
    match=re.search(r'certificate SHA-256 digest: ([a-f0-9]{64})',verified)
    if not match:raise BuildFailure('No se obtuvo el certificado del APK firmado.')
    return match[1]

def publish(snapshot,artifacts,state,output,sdk,key,password,log):
    with tempfile.TemporaryDirectory(prefix='package-',dir=state/'work') as temp:
        result=pipeline.assemble(snapshot,artifacts,Path(temp),sdk)
        signed=result/'Lucy.apk'
        certificate=sign_apk(sdk,key,password,result/'Lucy-unsigned.apk',signed)
        info=read_json(result/'build-info.json');info.update({'signed':True,'apk_sha256':tools.digest(signed),'certificate_sha256':certificate,
            'builder':'Lucy Builder Linux '+VERSION,'mode':snapshot.get('mode','main'),'compiler':snapshot['compiler']})
        save_json(result/'build-info.json',info)
        builds=output/'builds';builds.mkdir(exist_ok=True);name=time.strftime('%Y%m%d-%H%M%S')+'-'+snapshot['request_id'][:8]
        staging=builds/('.tmp-'+name);staging.mkdir()
        try:
            for source,target in [('Lucy.apk','Lucy.apk'),('Lucy-source.zip','Lucy-source.zip'),('build-info.json','build-info.json')]:shutil.copy2(result/source,staging/target)
            if log.is_file():shutil.copy2(log,staging/'build.log')
            final=builds/name;os.replace(staging,final)
            for filename in ['Lucy.apk','Lucy-source.zip','build-info.json','build.log']:
                link=output/filename
                if not link.is_symlink() and not link.exists():link.symlink_to(Path('latest')/filename)
            next_link=output/('.latest-'+uuid.uuid4().hex);next_link.symlink_to(Path('builds')/name,target_is_directory=True);os.replace(next_link,output/'latest')
        finally:shutil.rmtree(staging,ignore_errors=True)
    return output/'Lucy.apk'

def arguments():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',action='version',version='Lucy Builder Linux '+VERSION)
    p.add_argument('--state-dir',type=Path,default=Path(os.environ.get('LUCY_STATE_DIR',Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'lucy-builder')))
    p.add_argument('--output',type=Path,default=Path.cwd()/'Lucy-output')
    p.add_argument('--jobs',type=int,default=default_jobs())
    selection=p.add_mutually_exclusive_group()
    selection.add_argument('--verified',action='store_true',help='Usar explícitamente las revisiones base del perfil en lugar del main actual.')
    selection.add_argument('--repeat',action='store_true',help='Repetir las revisiones de la última ejecución, aunque main haya cambiado.')
    p.add_argument('--prepare-only',action='store_true',help='Descargar e integrar las fuentes, sin compilar ni instalar herramientas.')
    p.add_argument('--accept-sdk-license',action='store_true',help='Aceptar la licencia de Google SDK para automatización tras leerla.')
    p.add_argument('--rust-version',default='stable')
    p.add_argument('--import-key',type=Path,help='Firma anterior de Lucy: JKS, PKCS12 o ZIP de copia.')
    p.add_argument('--import-password-env',help='Variable que contiene la contraseña de la firma a importar; evita ponerla en argumentos.')
    p.add_argument('--key-alias',help='Alias si la copia de firma contiene varias claves privadas.')
    return p.parse_args()

class LogCapture:
    """Capture Python and child-process output together, without logging input."""
    def __init__(self,path):self.path=path
    def __enter__(self):
        sys.stdout.flush();sys.stderr.flush();self.out=os.dup(1);self.err=os.dup(2)
        self.reader,self.writer=os.pipe();self.sink=self.path.open('wb',buffering=0)
        def consume():
            while True:
                part=os.read(self.reader,65536)
                if not part:break
                self.sink.write(part)
                view=memoryview(part)
                while view:
                    wrote=os.write(self.out,view);view=view[wrote:]
        self.thread=threading.Thread(target=consume,daemon=True);self.thread.start()
        os.dup2(self.writer,1);os.dup2(self.writer,2);os.close(self.writer)
        return self
    def __exit__(self,typ,value,tb):
        if value is not None:print('ERROR: '+str(value),file=sys.stderr,flush=True)
        sys.stdout.flush();sys.stderr.flush();os.dup2(self.out,1);os.dup2(self.err,2)
        self.thread.join();self.sink.close();os.close(self.out);os.close(self.err);os.close(self.reader)


def main(args):
    tools.host_check()
    if args.jobs<1 or args.jobs>32:raise BuildFailure('--jobs debe estar entre 1 y 32.')
    state=args.state_dir.expanduser().resolve();state.mkdir(parents=True,exist_ok=True);state.chmod(0o700)
    lock=(state/'build.lock').open('a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise BuildFailure('Ya hay otra compilación de Lucy usando esta caché.')
    logs=state/'logs';logs.mkdir(exist_ok=True);log=logs/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.log')
    with LogCapture(log):
        try:
            output=output_root(args.output)
            print('Lucy Builder Linux '+VERSION+'\nSalida: '+str(output)+'\nRegistro: '+str(log),flush=True)
            print('1/6 · Seleccionando las revisiones de los cuatro proyectos…',flush=True)
            base=json.loads((pipeline.TEMPLATE/'engine-lock.json').read_text())
            request_id=uuid.uuid4().hex
            if args.repeat:
                snapshot=repeat_snapshot(base,read_json(state/'last-snapshot.json'),request_id)
            else:
                if args.verified:heads={e['id']:e['source_commit'] for e in base['engines']}
                else:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:heads=dict(zip(pipeline.REPOS,pool.map(pipeline.latest,pipeline.REPOS.values())))
                snapshot=pipeline.resolve_snapshot(heads,request_id,str(int(time.time()//60)))
            if args.verified:
                snapshot['engine_lock']['fonts']=copy.deepcopy(base['fonts'])
                snapshot['engine_lock']['translations']=copy.deepcopy(base['translations'])
            snapshot['mode']='repeat' if args.repeat else ('verified' if args.verified else 'main');snapshot['version_name']='0.11.'+time.strftime('%Y%m%d%H%M%S',time.gmtime())
            snapshot['version_code']=max(int(time.time()//60),read_json(output/'build-info.json',{}).get('version_code',0)+1)
            save_json(state/'last-snapshot.json',snapshot)
            print('2/6 · Descargando e integrando las fuentes…',flush=True)
            prepared=prepare(snapshot,state)
            if args.prepare_only:
                print('Fuentes listas en '+str(state/'work/engines')+'. No se compiló ninguna APK.',flush=True);return
            print('3/6 · Preparando las herramientas…',flush=True)
            sdk=tools.ensure_sdk(state,args.accept_sdk_license);java=tools.ensure_java(state);env,compiler=tools.ensure_rust(state,args.rust_version)
            env.update({'JAVA_HOME':str(java),'PATH':str(java/'bin')+os.pathsep+env['PATH'],'CARGO_BUILD_JOBS':str(args.jobs),'GIT_TERMINAL_PROMPT':'0'})
            old_env=dict(os.environ);os.environ.update(env)
            try:
                snapshot['compiler']=compiler;key,password=ensure_identity(state,env,java,args)
                shared_fonts(snapshot,prepared,state)
                print('4/6 · Compilando los cuatro editores…',flush=True)
                artifacts=compile_all(snapshot,prepared,state,compiler,args.jobs)
                print('5/6 · Empaquetando y firmando Lucy…',flush=True)
                apk=publish(snapshot,artifacts,state,output,sdk,key,password,log)
            finally:os.environ.clear();os.environ.update(old_env)
            print('6/6 · APK lista: '+str(apk)+'\nSHA-256: '+tools.digest(apk)+'\nGuardá una copia privada de '+str(state/'signing')+' para conservar tu firma.',flush=True)
        finally:pass

if __name__=='__main__':
    try:main(arguments())
    except KeyboardInterrupt:print('\nInterrumpido. Se conservan la firma, la caché válida y la última APK.',file=sys.stderr);sys.exit(130)
    except (BuildFailure,tools.SetupError,pipeline.BuildError,subprocess.CalledProcessError,OSError,ValueError) as error:
        print('\nNo se generó una APK nueva: '+str(error)+'\nLa última APK completa y tu firma se conservan.',file=sys.stderr);sys.exit(1)
