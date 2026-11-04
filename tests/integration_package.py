"""Build real, signed APKs from already source-compiled editor artifacts."""
from pathlib import Path
import copy,json,os,subprocess,sys
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import host
from app.worker import resolve,product_key
from app.core import bootstrap,legacy

state=Path(sys.argv[1]).resolve();output=Path(sys.argv[2]).resolve()
os.environ['JAVA_HOME']=str(bootstrap.ensure_java(state));os.environ['PATH']=os.environ['JAVA_HOME']+'/bin:'+os.environ['PATH']
sdk=bootstrap.ensure_sdk(state,True)
compiler=json.loads(next((state/'cache/engines/wordcraft').glob('*/engine.json')).read_text())
compiler_text=subprocess.check_output([state/'toolchains/cargo/bin/rustc','-Vv'],env={**os.environ,'CARGO_HOME':str(state/'toolchains/cargo'),'RUSTUP_HOME':str(state/'toolchains/rustup'),'RUSTUP_TOOLCHAIN':'1.99.1'},text=True).strip()
reports=[]
for mode,ids in [('lucy',['pdfcraft']),('lucy',['wordcraft','gridcraft']),('lucy',['wordcraft','pdfcraft','deckcraft']),('individual',['gridcraft'])]:
 snapshot=resolve(ids,'verified');snapshot['compiler']=compiler_text
 key,password=product_key(state,mode,ids[0],{},Path(os.environ['JAVA_HOME']))
 result=host.publish(snapshot,state/'work/artifacts',state,output,sdk,key,password,mode)
 with ZipFile(result['apk']) as archive:
  engines={Path(n).parts[2] for n in archive.namelist() if n.startswith('assets/engines/') and len(Path(n).parts)>3}
  assert engines==set(ids),(engines,ids)
  assert len([n for n in archive.namelist() if n.endswith('.wasm')])==len(ids)
  selection=json.loads(archive.read('assets/selection.json'));assert set(selection['engines'])==set(ids)
 badging=subprocess.check_output([sdk/'build-tools/36.0.0/aapt','dump','badging',result['apk']],text=True)
 assert "name='"+result['package_name']+"'" in badging
 reports.append({'mode':mode,'selection':ids,'apk_sha256':result['apk_sha256'],'certificate_sha256':result['certificate_sha256'],'bytes':Path(result['apk']).stat().st_size})
 print('PASS signed APK',mode,ids,Path(result['apk']).stat().st_size,flush=True)
(output/'integration-results.json').write_text(json.dumps(reports,indent=2))
