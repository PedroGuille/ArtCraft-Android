"""Regression for epoch timestamps in the installed Flatpak's source tree."""
from pathlib import Path
from zipfile import ZipFile
import os,sys,tempfile,time,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.host import archive_sources

class SourceArchiveTest(unittest.TestCase):
 def test_flatpak_epoch_preserves_content_permissions_and_input_date(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);project=root/'project';project.mkdir()
   source=project/'README.md';source.write_bytes(b'Source from Flatpak\n')
   source.chmod(0o640);os.utime(source,(0,0))
   archive_sources(project,root/'source.zip')
   with ZipFile(root/'source.zip') as archive:
    self.assertIsNone(archive.testzip())
    self.assertEqual(archive.read('source/README.md'),source.read_bytes())
    entry=archive.getinfo('source/README.md')
    self.assertEqual(entry.date_time,(1980,1,1,0,0,0))
    self.assertEqual((entry.external_attr>>16)&0o777,0o640)
   self.assertEqual(source.stat().st_mtime,0)

 def test_future_dates_are_clamped_and_build_outputs_remain_excluded(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);project=root/'project';project.mkdir()
   source=project/'LICENSE';source.write_bytes(b'License notice\n')
   future=4_733_856_000;os.utime(source,(future,future))
   normal=project/'normal.txt';normal.write_bytes(b'normal')
   timestamp=1_793_577_600;os.utime(normal,(timestamp,timestamp))
   for suffix in ['.p12','.pfx','.jks','.keystore','.apk','.pyc']:
    (project/('private'+suffix)).write_bytes(b'excluded')
   for directory in ['build','.cache','.git','__pycache__','engines']:
    path=project/directory;path.mkdir();(path/'excluded.txt').write_bytes(b'excluded')
   archive_sources(project,root/'source.zip')
   with ZipFile(root/'source.zip') as archive:
    self.assertEqual(set(archive.namelist()),{'source/LICENSE','source/normal.txt'})
    self.assertEqual(archive.getinfo('source/LICENSE').date_time[:3],(2107,12,31))
    expected=list(time.localtime(timestamp)[:6]);expected[5]-=expected[5]%2
    self.assertEqual(archive.getinfo('source/normal.txt').date_time,tuple(expected))
    self.assertEqual(archive.read('source/LICENSE'),source.read_bytes())
   self.assertEqual(source.stat().st_mtime,future)

if __name__=='__main__':unittest.main()
