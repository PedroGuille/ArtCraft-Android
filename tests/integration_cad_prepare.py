from pathlib import Path
import json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import ROOT,bootstrap
from app.worker import sources
from app.native_cad import load_module

state=Path(sys.argv[1]).resolve();folder,commit=sources('cadcraft',state,'main')
archive=state/'cache/native-source'/str(commit+'.zip');archive.parent.mkdir(parents=True,exist_ok=True)
if not archive.exists():subprocess.run(['git','archive','--format=zip','--prefix=cadcraft-'+commit+'/','--output='+str(archive),'HEAD'],cwd=folder,check=True)
tablet=load_module(ROOT/'native-cad/tablet.py','cad_prepare_test')
_,adapter_id=tablet.load_adapter(ROOT/'native-cad')
workspace=state/'work/cad-prepare-test'/str(commit+'-'+adapter_id[:12])
if workspace.exists():_,report=tablet.load_prepared(workspace,ROOT/'native-cad')
else:report=tablet.prepare(archive,workspace,ROOT/'native-cad')
print(json.dumps({'commit':commit,'version':report['upstream_version'],'status':report['status'],'conflicts':report['conflicts']},indent=2))
assert not report['conflicts']
