"""Exercise GTK job creation, streamed progress, cancellation and history."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,traceback
from unittest.mock import patch
sys.path.insert(0,os.environ.get('LUCY_TEST_ROOT',str(Path(__file__).resolve().parents[1])))
from app.gui import BuilderWindow,Gtk,Adw,Gio,GLib

Gtk.init();app=Adw.Application(application_id='io.github.pedroguille.LucyBuilder.Workflow',flags=Gio.ApplicationFlags.NON_UNIQUE);app.register(None)
temporary=tempfile.TemporaryDirectory();state=Path(temporary.name);window=BuilderWindow(app,state/'data');window.output_entry.set_text(str(state/'output'));window.present();loop=GLib.MainLoop();failures=[];calls=[];real_popen=subprocess.Popen

def launch(arguments,**kwargs):
 request=json.loads(Path(arguments[arguments.index('--job')+1]).read_text());calls.append(request)
 assert request['apps']==['pdfcraft'] and request['mode']=='lucy' and request['download_only'] is True
 assert 'password' not in json.dumps(request)
 if len(calls)==1:program="import json,time;print('@LUCY '+json.dumps({'event':'stage','fraction':.42,'title':'Probando progreso'}),flush=True);time.sleep(40)"
 else:program="import json;print('@LUCY '+json.dumps({'event':'sources','paths':[]}),flush=True)"
 return real_popen([sys.executable,'-u','-c',program],**kwargs)

def finish(error=None):
 if error:failures.append(error);traceback.print_exc()
 if window.process:window.cancel()
 window.destroy();loop.quit();return False

def start():
 try:
  for name,check in window.office_checks.items():check.set_active(name=='pdfcraft')
  window.start('lucy',True)
  assert not window.lucy_button.get_sensitive()
  GLib.timeout_add(1300,cancel)
 except Exception as error:return finish(error)
 return False

def cancel():
 try:assert abs(window.progress.get_fraction()-.42)<.01;window.cancel();GLib.timeout_add(100,wait_cancel)
 except Exception as error:return finish(error)
 return False

def wait_cancel():
 if window.process:return True
 try:
  assert window.history[0]['status']=='cancelled';assert window.lucy_button.get_sensitive()
  window.start('lucy',True);GLib.timeout_add(100,wait_success)
 except Exception as error:return finish(error)
 return False

def wait_success():
 if window.process:return True
 try:
  assert window.history[0]['status']=='success';assert len(calls)==2
  persisted=json.loads((state/'data/history.json').read_text());assert [j['status'] for j in persisted]==['success','cancelled']
  print('PASS GTK workflow: exact job selection, streamed progress, cancellation, retry and persistent history')
 except Exception as error:return finish(error)
 return finish()

with patch('app.gui.subprocess.Popen',side_effect=launch):
 GLib.timeout_add(500,start);GLib.timeout_add_seconds(20,lambda:finish(RuntimeError('GUI workflow timeout')));loop.run()
temporary.cleanup();sys.exit(bool(failures))
