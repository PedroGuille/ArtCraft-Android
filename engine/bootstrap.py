"""Private, checksum-verified Linux build tools. No Android app or GitHub login."""
from __future__ import annotations
import hashlib,json,os,platform,re,shutil,stat,subprocess,sys,tarfile,time
from pathlib import Path,PurePosixPath
import urllib.request,urllib.parse,urllib.error
import xml.etree.ElementTree as ET
from zipfile import ZipFile

SDK_METADATA='https://dl.google.com/android/repository/repository2-1.xml'
TARGET='wasm32-unknown-unknown'

class SetupError(Exception):pass

def atomic(path:Path,data:bytes,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    try:
        with temp.open('wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        temp.chmod(mode);os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)

def digest(path,algorithm='sha256'):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,algorithm).hexdigest()

def data_url(url,limit=8*1024*1024):
    if urllib.parse.urlsplit(url).scheme!='https':raise SetupError('La descarga requiere HTTPS.')
    req=urllib.request.Request(url,headers={'User-Agent':'Lucy-Builder-Linux/1.0.0','Accept':'application/json, */*'})
    with urllib.request.urlopen(req,timeout=90) as response:data=response.read(limit+1)
    if len(data)>limit:raise SetupError('Metadatos de descarga demasiado grandes.')
    return data

def download(url,destination,expected,algorithm='sha256',limit=2*1024*1024*1024):
    if urllib.parse.urlsplit(url).scheme!='https':raise SetupError('La descarga requiere HTTPS.')
    destination=Path(destination)
    if not re.fullmatch('[a-f0-9]{'+str(hashlib.new(algorithm).digest_size*2)+'}',expected):raise SetupError('Hash de herramienta no válido.')
    if destination.is_file() and digest(destination,algorithm)==expected:return destination
    destination.parent.mkdir(parents=True,exist_ok=True)
    part=destination.with_name(destination.name+'.part-'+str(os.getpid()))
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Lucy-Builder-Linux/1.0.0'})
        with urllib.request.urlopen(req,timeout=180) as src,part.open('wb') as out:
            count=0;reported=0;h=hashlib.new(algorithm)
            while block:=src.read(1024*1024):
                count+=len(block)
                if count>limit:raise SetupError('La herramienta supera el tamaño esperado.')
                h.update(block);out.write(block)
                if count-reported>=16*1024*1024:
                    print(f'  {destination.name}: {count//(1024*1024)} MiB',flush=True);reported=count
            out.flush();os.fsync(out.fileno())
        if h.hexdigest()!=expected:raise SetupError('No coincide el checksum de '+destination.name)
        os.replace(part,destination);return destination
    finally:part.unlink(missing_ok=True)

def unzip(archive,destination,strip_first=False):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);base=destination.resolve()
    with ZipFile(archive) as z:
        infos=z.infolist()
        if len(infos)>200000 or sum(i.file_size for i in infos)>4*1024**3:raise SetupError('Paquete SDK demasiado grande.')
        seen=set()
        for info in infos:
            rel=PurePosixPath(info.filename)
            if rel.is_absolute() or '..' in rel.parts or '\\' in info.filename:raise SetupError('Ruta no permitida en el SDK.')
            parts=rel.parts[1:] if strip_first else rel.parts
            if not parts:continue
            target=destination.joinpath(*parts)
            if not target.resolve().is_relative_to(base) or target in seen:raise SetupError('Ruta repetida o fuera del SDK.')
            seen.add(target);mode=info.external_attr>>16
            if stat.S_ISLNK(mode):raise SetupError('No se admiten enlaces en el ZIP del SDK.')
            if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
            target.chmod((mode&0o777) or 0o644)

def sdk_packages(xml):
    root=ET.fromstring(xml);wanted={'platforms;android-36':('platforms/android-36','platform-36_r02.zip'),
                                  'build-tools;36.0.0':('build-tools/36.0.0','build-tools_r36_linux.zip')}
    licenses={e.attrib['id']:''.join(e.itertext()).strip() for e in root if e.tag.rsplit('}',1)[-1]=='license'}
    result=[]
    for package in root:
        name=package.attrib.get('path')
        if name not in wanted:continue
        dest,filename=wanted[name]
        for a in package.findall('archives/archive'):
            if a.findtext('host-os') not in {None,'linux'} or a.findtext('complete/url')!=filename:continue
            ref=package.find('uses-license');license_id=ref.attrib['ref'] if ref is not None else None
            if license_id not in licenses:raise SetupError('No se encontró la licencia del SDK.')
            result.append({'name':name,'destination':dest,'filename':filename,'sha1':a.findtext('complete/checksum'),
                           'license_id':license_id,'license_text':licenses[license_id]})
    if len(result)!=2:raise SetupError('Los paquetes SDK fijados ya no aparecen en el repositorio oficial.')
    return result

def ensure_sdk(state,accept=False):
    root=Path(state)/'tools/android-sdk';receipt=root/'lucy-license-receipt.json'
    expected=['platforms/android-36/android.jar','build-tools/36.0.0/aapt2','build-tools/36.0.0/lib/apksigner.jar','build-tools/36.0.0/zipalign','build-tools/36.0.0/d8']
    record=root/'lucy-sdk.json'
    if record.is_file() and receipt.is_file():
        meta=json.loads(record.read_text())
        if all((root/name).is_file() and digest(root/name)==meta.get('files',{}).get(name) for name in expected):return root
    print('Preparando Android SDK 36…',flush=True)
    packages=sdk_packages(data_url(SDK_METADATA))
    consent={}
    if receipt.is_file():consent=json.loads(receipt.read_text()).get('licenses',{})
    licenses={p['license_id']:p['license_text'] for p in packages}
    for name,text in licenses.items():
        license_path=root/'licenses'/str(name+'.txt');atomic(license_path,text.encode())
        checksum=hashlib.sha256(text.encode()).hexdigest()
        if consent.get(name)!=checksum:
            if not accept:
                print('El SDK de Android requiere aceptar su licencia de Google.\nTexto completo: '+str(license_path)+'\nReferencia: https://developer.android.com/studio/terms',flush=True)
                if not sys.stdin.isatty() or input('¿Aceptás esa licencia para instalar el SDK? [s/N] ').strip().lower() not in {'s','si','sí','y','yes'}:
                    raise SetupError('Licencia no aceptada. Para uso automatizado, leela y usá --accept-sdk-license.')
            consent[name]=checksum
    atomic(receipt,json.dumps({'licenses':consent,'accepted_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},indent=2).encode())
    for item in packages:
        archive=download('https://dl.google.com/android/repository/'+item['filename'],Path(state)/'downloads'/item['filename'],item['sha1'],'sha1')
        destination=root/item['destination']
        if destination.exists():shutil.rmtree(destination)
        unzip(archive,destination,True)
    tools=root/'build-tools/36.0.0'
    for name in ['aapt','aapt2','aidl','apksigner','d8','zipalign']:
        p=tools/name
        if p.is_file():p.chmod(p.stat().st_mode|0o111)
    atomic(record,json.dumps({'packages':[{k:v for k,v in p.items() if k!='license_text'} for p in packages],
                              'files':{n:digest(root/n) for n in expected}},indent=2).encode())
    return root

def valid_java(path):
    try:
        executable=Path(path).resolve();home=executable.parent.parent
        if not (home/'bin/keytool').is_file():return None
        modules=subprocess.check_output([str(executable),'--list-modules'],stderr=subprocess.DEVNULL,text=True)
        match=re.search(r'(?m)^java.base@(\d+)',modules)
        if match and int(match[1])>=17 and 'jdk.compiler@' in modules:return home
    except (OSError,subprocess.CalledProcessError):pass
    return None

def jdk_asset():
    try:
        items=json.loads(data_url('https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=linux&vendor=eclipse'))
        p=items[0]['binary']['package'];return {'url':p['link'],'sha256':p['checksum'],'name':p['name']}
    except (OSError,ValueError,KeyError,IndexError):
        # Same official vendor, mirrored in its own public GitHub release.
        data=json.loads(data_url('https://api.github.com/repos/adoptium/temurin17-binaries/releases/latest'))
        package=next(a for a in data['assets'] if re.fullmatch(r'OpenJDK17U-jdk_x64_linux_hotspot_.+\.tar\.gz',a['name']))
        sha_asset=next(a for a in data['assets'] if a['name']==package['name']+'.sha256.txt')
        checksum=data_url(sha_asset['browser_download_url']).decode().split()[0]
        return {'url':package['browser_download_url'],'sha256':checksum,'name':package['name']}

def ensure_java(state):
    current=shutil.which('java')
    if current and (home:=valid_java(current)):return home
    root=Path(state)/'tools/jdk';record=root/'lucy-jdk.json'
    if record.is_file():
        info=json.loads(record.read_text());home=root/info['directory']
        if valid_java(home/'bin/java'):return home
    print('Descargando un JDK 17 oficial, sin modificar Java del sistema…',flush=True)
    item=jdk_asset();archive=download(item['url'],Path(state)/'downloads'/item['name'],item['sha256'])
    root.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive) as tar:
        # data filter rejects escaping links, devices and absolute traversal.
        if not hasattr(tarfile,'data_filter'):raise SetupError('Actualizá Python 3.11 a su última revisión de seguridad para extraer el JDK.')
        tar.extractall(root,filter='data')
    homes=[p.parent.parent for p in root.glob('*/bin/java') if valid_java(p)]
    if len(homes)!=1:raise SetupError('El JDK descargado no tiene la estructura esperada.')
    atomic(record,json.dumps({**item,'directory':homes[0].name},indent=2).encode())
    return homes[0]

def ensure_rust(state,toolchain='stable'):
    if not re.fullmatch(r'stable|\d+\.\d+\.\d+',toolchain):raise SetupError('Versión Rust no válida.')
    cargo=Path(state)/'toolchains/cargo';rustup=Path(state)/'toolchains/rustup';binary=cargo/'bin/rustup'
    env={**os.environ,'CARGO_HOME':str(cargo),'RUSTUP_HOME':str(rustup),'RUSTUP_TOOLCHAIN':toolchain,
         'RUSTC':str(cargo/'bin/rustc'),'RUSTDOC':str(cargo/'bin/rustdoc'),
         'PATH':str(cargo/'bin')+os.pathsep+os.environ.get('PATH','')}
    if not binary.is_file():
        print('Instalando Rust oficial y su biblioteca WebAssembly correspondiente…',flush=True)
        url='https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init'
        checksum=data_url(url+'.sha256').decode().split()[0]
        installer=download(url,Path(state)/'downloads/rustup-init',checksum);installer.chmod(0o755)
        subprocess.run([str(installer),'-y','--no-modify-path','--profile','minimal','--default-toolchain',toolchain,'--target',TARGET],env=env,check=True)
    else:
        subprocess.run([str(binary),'toolchain','install',toolchain,'--profile','minimal','--target',TARGET],env=env,check=True)
    version=subprocess.check_output([str(cargo/'bin/rustc'),'-Vv'],env=env,text=True).strip()
    target_dir=subprocess.check_output([str(cargo/'bin/rustc'),'--print','target-libdir','--target',TARGET],env=env,text=True).strip()
    if not Path(target_dir).is_relative_to(rustup) or not list(Path(target_dir).glob('libstd-*.rlib')):
        raise SetupError('La biblioteca WebAssembly no pertenece al compilador seleccionado.')
    return env,version

def host_check():
    if sys.platform!='linux' or platform.machine().lower() not in {'x86_64','amd64'}:raise SetupError('Esta edición del constructor necesita Linux x86_64.')
    if sys.version_info<(3,11):raise SetupError('Se necesita Python 3.11 o posterior.')
    missing=[n for n in ['git','cc','c++','make'] if not shutil.which(n)]
    if missing:raise SetupError('Faltan herramientas base: '+', '.join(missing)+'.\nFedora: sudo dnf install python3 git gcc gcc-c++ make\nUbuntu/Debian: sudo apt install python3 git build-essential')
