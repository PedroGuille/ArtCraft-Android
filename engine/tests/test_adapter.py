"""Check the source merge against real, small Git repositories."""
from pathlib import Path
import subprocess,tempfile,unittest,sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lucy import pipeline

class AdapterTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def git(self,folder,*args):return subprocess.check_output(['git',*args],cwd=folder,text=True,stderr=subprocess.DEVNULL).strip()
 def fixture(self,conflict=False):
  origin=self.root/'origin';origin.mkdir();self.git(origin,'init','--quiet');self.git(origin,'config','user.name','Fixture');self.git(origin,'config','user.email','fixture@example.invalid')
  catalog=origin/'crates/ui-egui/src/i18n';catalog.mkdir(parents=True)
  for name in ['es','fr','mod']:(catalog/(name+'.rs')).write_text('catalog '+name)
  (origin/'Cargo.toml').write_text('[workspace.package]\nversion="1.0.0"\n')
  code=origin/'integration.rs';code.write_text(''.join('line'+str(i)+'\n' for i in range(30)))
  self.git(origin,'add','.');self.git(origin,'commit','--quiet','-m','baseline');base=self.git(origin,'rev-parse','HEAD')
  code.write_text(code.read_text().replace('line3\n','Lucy compact menu\n'));adaptation=subprocess.check_output(['git','diff','--binary','HEAD'],cwd=origin)
  self.git(origin,'reset','--hard','HEAD');code.write_text(code.read_text().replace('line3\n' if conflict else 'line25\n','New upstream functionality\n'))
  self.git(origin,'add','.');self.git(origin,'commit','--quiet','-m','new main');head=self.git(origin,'rev-parse','HEAD')
  project=self.root/'project';(project/'third_party/patches').mkdir(parents=True);(project/'third_party/patches/gridcraft.patch').write_bytes(adaptation)
  engine={'id':'gridcraft','source_commit':head,'adapter_base_commit':base,'source_prune':[]}
  def clone(repo,commit,folder,extra_commit=None):
   folder.parent.mkdir(parents=True,exist_ok=True);subprocess.run(['git','clone','--quiet','--no-hardlinks',str(origin),str(folder)],check=True);self.git(folder,'checkout','--quiet','--detach',commit)
  return engine,project,clone
 def test_merge_keeps_new_upstream_code_and_spanish(self):
  engine,project,clone=self.fixture()
  with patch.object(pipeline,'clone_commit',clone):source=pipeline.apply_adapter(engine,project,self.root/'sources')
  text=(source/'integration.rs').read_text();self.assertIn('Lucy compact menu',text);self.assertIn('New upstream functionality',text)
  self.assertFalse((source/'crates/ui-egui/src/i18n/fr.rs').exists());self.assertTrue((source/'crates/ui-egui/src/i18n/es.rs').exists());self.assertTrue((source/'crates/ui-egui/src/i18n/mod.rs').exists())
  self.assertEqual(engine['version'],'1.0.0')
 def test_conflict_stops_the_build(self):
  import compatibility
  engine,project,clone=self.fixture(True)
  with patch.object(compatibility,'profile',return_value=None),patch.object(pipeline,'clone_commit',clone),self.assertRaisesRegex(pipeline.BuildError,'actualizar el adaptador'):
   pipeline.apply_adapter(engine,project,self.root/'sources')
  self.assertFalse((project/'app/src/main/assets/engines').exists())

 def test_reviewed_adapter_keeps_new_code_after_legacy_conflict(self):
  import compatibility
  engine,project,clone=self.fixture(True)
  origin=self.root/'origin';code=origin/'integration.rs'
  code.write_text(code.read_text().replace('New upstream functionality','New upstream functionality + Lucy compact menu'))
  reviewed=self.root/'reviewed.patch';reviewed.write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=origin))
  candidate={'path':reviewed,'base_commit':engine['source_commit'],'source_prune':[]}
  engine['language_mode']='all'
  with patch.object(pipeline,'clone_commit',clone),patch.object(compatibility,'profile',return_value=candidate):
   source=pipeline.apply_adapter(engine,project,self.root/'sources')
  self.assertIn('New upstream functionality + Lucy compact menu',(source/'integration.rs').read_text())
  self.assertEqual(engine['adapter_profile'],'2026-11-06')
  self.assertTrue((source/'crates/ui-egui/src/i18n/fr.rs').exists())

 def test_reviewed_adapter_cannot_hide_a_new_conflict(self):
  import compatibility
  engine,project,clone=self.fixture(True)
  candidate={'path':project/'third_party/patches/gridcraft.patch','base_commit':engine['adapter_base_commit'],'source_prune':[]}
  with patch.object(pipeline,'clone_commit',clone),patch.object(compatibility,'profile',return_value=candidate),self.assertRaises(pipeline.BuildError):
   pipeline.apply_adapter(engine,project,self.root/'sources')


 def test_exact_reviewed_adapter_wins_even_when_legacy_merge_is_clean(self):
  import compatibility
  engine,project,clone=self.fixture(False)
  origin=self.root/'origin';code=origin/'integration.rs'
  code.write_text(code.read_text().replace('line3\n','Lucy current API\n'))
  reviewed=self.root/'current.patch';reviewed.write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=origin))
  candidate={'path':reviewed,'base_commit':engine['source_commit'],'source_prune':[],'reviewed_at':'2026-11-09'}
  engine['language_mode']='all'
  with patch.object(pipeline,'clone_commit',clone),patch.object(compatibility,'profile',return_value=candidate):
   source=pipeline.apply_adapter(engine,project,self.root/'sources')
  text=(source/'integration.rs').read_text()
  self.assertIn('Lucy current API',text)
  self.assertNotIn('Lucy compact menu',text)
  self.assertIn('New upstream functionality',text)
  self.assertEqual(engine['adapter_profile'],'2026-11-09')

if __name__=='__main__':unittest.main()
