"""Source adapter failures must precede compiler downloads and signing."""
from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import worker

class PreflightTest(unittest.TestCase):
 def test_cad_verified_revision_does_not_refresh_main(self):
  with tempfile.TemporaryDirectory() as temp:
   state=Path(temp);commit=json.loads((worker.ROOT/'app/verified.json').read_text())['heads']['cadcraft']
   with patch.object(worker.pipeline,'latest',side_effect=AssertionError('Verified CAD must remain pinned')),patch.object(worker.pipeline,'clone_commit') as clone:
    folder,actual=worker.sources('cadcraft',state,'verified')
   self.assertEqual(actual,commit)
   clone.assert_called_once_with('storytold/cadcraft',commit,folder)

 def test_cad_main_still_resolves_current_upstream(self):
  with tempfile.TemporaryDirectory() as temp:
   state=Path(temp);commit='b'*40
   with patch.object(worker.pipeline,'latest',return_value=commit) as latest,patch.object(worker.pipeline,'clone_commit') as clone:
    folder,actual=worker.sources('cadcraft',state,'main')
   latest.assert_called_once_with('storytold/cadcraft')
   self.assertEqual(actual,commit)
   clone.assert_called_once_with('storytold/cadcraft',commit,folder)

 def test_conflict_does_not_install_tools_or_create_key(self):
  with tempfile.TemporaryDirectory() as temp:
   state=Path(temp);tools=Mock();snapshot={'heads':{'wordcraft':'a'*40}}
   with patch.object(worker,'resolve',return_value=snapshot),patch.object(worker.legacy,'prepare',side_effect=ValueError('adapter conflict')),patch.object(worker,'product_key') as key,patch.object(worker,'emit'):
    with self.assertRaisesRegex(ValueError,'adapter conflict'):
     worker.office(('wordcraft',),state,state,{'revision_mode':'main'},tools)
    tools.assert_not_called();key.assert_not_called()

 def test_success_resolves_sources_before_tools(self):
  with tempfile.TemporaryDirectory() as temp:
   state=Path(temp);order=[];snapshot={'heads':{'wordcraft':'a'*40}}
   tools=Mock(side_effect=lambda:(order.append('tools') or (state,state,'rustc')))
   with patch.object(worker,'resolve',return_value=snapshot),patch.object(worker.legacy,'prepare',side_effect=lambda *args:(order.append('sources') or {})),patch.object(worker,'product_key',return_value=(state/'key',state/'password')),patch.object(worker.legacy,'shared_fonts'),patch.object(worker.legacy,'compile_all',return_value=state),patch.object(worker.host,'publish',return_value={'apk':'Lucy.apk'}),patch.object(worker,'emit'):
    worker.office(('wordcraft',),state,state,{'revision_mode':'main','mode':'lucy','jobs':1},tools)
   self.assertEqual(order,['sources','tools']);tools.assert_called_once()

if __name__=='__main__':unittest.main()
