from pathlib import Path
import os,sys,tempfile,traceback,subprocess
sys.path.insert(0,os.environ.get('LUCY_TEST_ROOT',str(Path(__file__).resolve().parents[1])))
from app.gui import BuilderWindow,Gtk,Adw,Gio,GLib,Gdk
Gtk.init();app=Adw.Application(application_id='io.github.pedroguille.LucyBuilder.Test',flags=Gio.ApplicationFlags.NON_UNIQUE);app.register(None)
temporary=tempfile.TemporaryDirectory();window=BuilderWindow(app,Path(temporary.name));window.present();loop=GLib.MainLoop();failures=[]
def check():
 try:
  assert len(window.cards)==15
  assert sum(c.get_active() for c in window.office_checks.values())==4
  for mask in range(1,16):
   for index,check in enumerate(window.office_checks.values()):check.set_active(bool(mask&(1<<index)))
   assert window.lucy_button.get_sensitive()
   assert window.suite_count.get_text().startswith(str(mask.bit_count()))
  for check in window.office_checks.values():check.set_active(False)
  assert not window.lucy_button.get_sensitive()
  for check in window.office_checks.values():check.set_active(True)
  window.select_all();assert window.individual_button.get_sensitive()
  window.cards['craft-anything'].set_active(True);assert not window.individual_button.get_sensitive();assert window.download_button.get_sensitive()
  window.select_all(False);window.cards['wordcraft'].set_active(True)
  window.switch('lucy')
  assert window.get_visible() and window.get_width()>800
  print('PASS native GTK UI: 15 catalog cards, all 15 Lucy selections, zero-selection guard, source-only apps and preview')
 except Exception as error:failures.append(error);traceback.print_exc()
 GLib.timeout_add(600,capture)
 return False
def capture():
 try:subprocess.run(['import','-window','root',os.environ.get('LUCY_SCREENSHOT','/tmp/lucy-builder-gui.png')],check=True,timeout=20)
 except Exception as error:failures.append(error);traceback.print_exc()
 finally:window.destroy();loop.quit()
 return False
GLib.timeout_add(1800,check);loop.run();temporary.cleanup()
sys.exit(bool(failures))
