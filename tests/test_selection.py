"""Verify composition affects the packaged host, rather than just the GUI."""
from pathlib import Path
import itertools,json,subprocess,sys,tempfile,unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.catalog import APPS,OFFICE,selection
from app.core import pipeline
from app.host import configure,NS,MIME

class CompositionTest(unittest.TestCase):
 def test_reject_bad_selections(self):
  for mode,ids in [('lucy',[]),('lucy',['wordcraft','wordcraft']),('lucy',['cadcraft']),('individual',[{}]),('individual',['unknown']),('other',['wordcraft'])]:
   with self.subTest(mode=mode,ids=ids),self.assertRaises(ValueError):selection(mode,ids)

 def test_all_fifteen_combinations(self):
  for size in range(1,5):
   for ids in itertools.combinations(OFFICE,size):
    with self.subTest(ids=ids),tempfile.TemporaryDirectory() as tmp:
     project=Path(tmp)/'project';pipeline.copy_template(project);title,package,slug=configure(project,'lucy',ids)
     assets=project/'app/src/main/assets';data=json.loads((assets/'selection.json').read_text())
     self.assertEqual(data['engines'],list(ids));self.assertEqual(package,'io.github.pedroguille.folio')
     html=(assets/'index.html').read_text();javascript=(assets/'shell.js').read_text()
     catalog=json.loads(javascript.split('  const engines = ',1)[1].split(';',1)[0])
     self.assertEqual(set(catalog),set(ids))
     for name in OFFICE:self.assertEqual('data-new="'+name+'"' in html,name in ids)
     tree=ET.parse(project/'app/src/main/AndroidManifest.xml')
     actual={d.get(NS+'mimeType') for d in tree.findall('application/activity/intent-filter/data')}
     self.assertEqual(actual,{mime for name in ids for mime in MIME[name]})
     subprocess.run([sys.executable,str(project/'scripts/create_templates.py')],check=True,stdout=subprocess.DEVNULL)
     expected={t for name,t in [('wordcraft','blank.docx'),('pdfcraft','blank.pdf'),('gridcraft','blank.xlsx')] if name in ids}
     self.assertEqual({p.name for p in (assets/'templates').iterdir()},expected)

 def test_individual_identity_and_icon(self):
  for app in APPS:
   if app.recipe in {'native','source'}:continue
   with self.subTest(app=app.id),tempfile.TemporaryDirectory() as tmp:
    project=Path(tmp)/'project';pipeline.copy_template(project);title,package,slug=configure(project,'individual',[app.id])
    self.assertEqual(title,app.name);self.assertEqual(slug,app.id)
    self.assertEqual(package,'io.github.pedroguille.'+app.id.replace('-',''))
    manifest=ET.parse(project/'app/src/main/AndroidManifest.xml')
    self.assertEqual(manifest.getroot().get('package'),package)
    for source in (project/'app/src/main/java').rglob('*.java'):
     self.assertIn('package '+package+';',source.read_text())
    self.assertTrue((project/'app/src/main/res/drawable-nodpi/lucy_icon.png').is_file())

if __name__=='__main__':unittest.main(verbosity=2)
