"""Use the existing native tablet port for CADCraft, not a desktop binary."""
from pathlib import Path
import importlib.util,json,os,re,shutil,subprocess,time,uuid
from .core import ROOT,legacy,bootstrap

def load_module(path,name):
 import sys
 sys.path.insert(0,str(path.parent));spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def build(state,output,job,tools):
 from .worker import emit,sources,product_key
 sdk,java,compiler=tools;source,commit=sources('cadcraft',state,job['revision_mode']);emit('revisions',heads={'cadcraft':commit})
 template=ROOT/'native-cad';digest=legacy.key_of({name:bootstrap.digest(template/name) for name in ['adapter.json','tablet.py','linux.py']})
 kit=state/'native-cad'/digest
 if not kit.exists():shutil.copytree(template,kit,ignore=shutil.ignore_patterns('__pycache__','.git','cache','work','dist','*.keystore','*.p12','*.jks'))
 tablet=load_module(kit/'tablet.py','cad_tablet');linux=load_module(kit/'linux.py','cad_linux')
 archive=state/'cache/native-source'/str(commit+'.zip');archive.parent.mkdir(parents=True,exist_ok=True)
 if not archive.exists():subprocess.run(['git','archive','--format=zip','--prefix=cadcraft-'+commit+'/','--output='+str(archive),'HEAD'],cwd=source,check=True)
 adapter,adapter_id=tablet.load_adapter(kit);workspace=kit/'work'/str(commit[:16]+'-'+adapter_id[:12])
 emit('stage',fraction=.12,title='Integrando CADCraft para Android')
 if workspace.exists():_,report=tablet.load_prepared(workspace,kit)
 else:report=tablet.prepare(archive,workspace,kit)
 if report['conflicts']:raise ValueError('La versión actual de CADCraft necesita actualizar su adaptador: '+', '.join(str(x) for x in report['conflicts']))
 native=state/'tools/native-cad';native.mkdir(parents=True,exist_ok=True)
 for name,target in [('cargo',state/'toolchains/cargo'),('rustup',state/'toolchains/rustup')]:
  link=native/name
  if not link.exists():link.symlink_to(target,target_is_directory=True)
 android=native/'android';android.mkdir(exist_ok=True)
 for name in ['platforms','build-tools']:
  link=android/name
  if not link.exists():link.symlink_to(sdk/name,target_is_directory=True)
 for path in [sdk/'platforms/android-36',sdk/'build-tools/36.0.0']:(path/'.complete').touch()
 env=linux.build_env(kit,job['jobs']);env.update(CADCRAFT_TOOLCHAIN_ROOT=str(native),JAVA_HOME=str(java),RUSTUP_HOME=str(native/'rustup'),CARGO_HOME=str(native/'cargo'),ANDROID_HOME=str(android),ANDROID_NDK_HOME=str(android/'android-ndk-r28c'))
 env['PATH']=str(java/'bin')+os.pathsep+str(native/'cargo/bin')+os.pathsep+os.environ.get('PATH','')
 emit('stage',fraction=.20,title='Preparando Android NDK para CADCraft')
 subprocess.run(['bash',str(kit/'tools/install-toolchain.sh')],env=env,check=True)
 key,password=product_key(state,'individual','cadcraft',job,java)
 exported=kit/'private/preview.keystore';exported.parent.mkdir(exist_ok=True);temporary=exported.with_suffix('.new.keystore');temporary.unlink(missing_ok=True)
 scope={**env,'LUCY_NATIVE_SOURCE_PASSWORD':password.read_text(),'LUCY_NATIVE_DEST_PASSWORD':'android'}
 legacy.run([java/'bin/keytool','-importkeystore','-srckeystore',key,'-srcstoretype','PKCS12','-srcstorepass:env','LUCY_NATIVE_SOURCE_PASSWORD','-srcalias','lucy','-destkeystore',temporary,'-deststoretype','JKS','-destalias','androiddebugkey','-deststorepass:env','LUCY_NATIVE_DEST_PASSWORD','-destkeypass:env','LUCY_NATIVE_DEST_PASSWORD','-noprompt'],scope,True)
 temporary.chmod(0o600);os.replace(temporary,exported)
 artifacts=kit/'dist'/str(commit[:12]+'-'+uuid.uuid4().hex[:8]);emit('stage',fraction=.30,title='Compilando CADCraft nativo · ARM64')
 with linux.environment(env):result=tablet.compile_prepared(workspace,artifacts,'arm64-v8a',exported,kit=kit)
 apk=Path(result['apk']);verified=legacy.run([sdk/'build-tools/36.0.0/apksigner','verify','--verbose','--print-certs',apk],capture=True)
 if 'v2 scheme (APK Signature Scheme v2): true' not in verified:raise ValueError('La firma de CADCraft no se verificó.')
 certificate=re.search(r'certificate SHA-256 digest: ([a-f0-9]{64})',verified)
 if not certificate:raise ValueError('No se obtuvo el certificado de CADCraft.')
 product=output/'cadcraft'
 if product.is_symlink():raise ValueError('La carpeta CADCraft de salida no puede ser un enlace.')
 product.mkdir(parents=True,exist_ok=True);final=product/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);final.mkdir()
 target=final/'CADCraft.apk';shutil.copy2(apk,target);shutil.copy2(result['symbols'],final/'CADCraft-symbols.zip')
 info={'builder':'Lucy Builder 2.3.2','mode':'individual','source_selection':job['revision_mode'],'selection':['cadcraft'],'name':'CADCraft','heads':{'cadcraft':commit},'version_name':result['upstream_version'],'apk':str(target),'output':str(final),'source':str(workspace),'report':str(final/'build-info.json'),'apk_sha256':bootstrap.digest(target),'certificate_sha256':certificate[1],'abi':'arm64-v8a','recipe':'native-tablet','adapter_version':adapter['adapter_version'],'adapter_profile':report.get('source_profile','legacy'),'physical_device_tested':False}
 legacy.save_json(final/'build-info.json',info);return info
