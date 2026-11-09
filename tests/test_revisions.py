"""Source option migration and offline reproducibility regressions."""
import json, unittest
from pathlib import Path
from unittest.mock import patch
from app import revisions, worker

class RevisionTests(unittest.TestCase):
    def test_new_install_uses_reviewed_sources(self):
        self.assertEqual(revisions.MODES[revisions.selected_index({})], 'reviewed')
    def test_previous_schema_preserves_all_three_choices(self):
        for value, expected in enumerate(('verified', 'release', 'main')):
            with self.subTest(value=value):
                self.assertEqual(revisions.MODES[revisions.selected_index({'revision_schema':2,'revision_mode':value})], expected)
    def test_legacy_settings_preserve_main(self):
        self.assertEqual(revisions.MODES[revisions.selected_index({'revision_mode':0})], 'main')
    def test_invalid_settings_choose_reviewed(self):
        for value in (None, '2', True, -1, 4):
            self.assertEqual(revisions.selected_index({'revision_schema':3,'revision_mode':value}),0)
    def test_current_schema_retains_each_selection(self):
        for value in range(len(revisions.MODES)):
            self.assertEqual(revisions.selected_index({'revision_schema':3,'revision_mode':value}),value)
    def test_reviewed_snapshot_never_asks_for_latest_sources(self):
        saved=json.loads((Path(worker.ROOT)/'app/reviewed.json').read_text())
        with patch.object(worker.pipeline,'latest',side_effect=AssertionError('A frozen build contacted main')):
            snapshot=worker.resolve(['wordcraft','pdfcraft','gridcraft'],'reviewed','all')
        self.assertEqual(snapshot['heads'],{key:saved['heads'][key] for key in ('wordcraft','pdfcraft','gridcraft')})
        self.assertEqual(snapshot['engine_lock']['fonts'],saved['fonts'])
        self.assertEqual(snapshot['engine_lock']['translations'],saved['translations'])
        self.assertEqual(worker.revision('cadcraft','reviewed'),saved['heads']['cadcraft'])

if __name__=='__main__':unittest.main()
