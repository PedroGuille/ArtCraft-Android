"""A saved current-source constructor must also support another CI build."""
import importlib.util, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lucy_current_source_update',ROOT/'tools/current_sources.py')
update=importlib.util.module_from_spec(spec);spec.loader.exec_module(update)

class PreparationTests(unittest.TestCase):
    def test_already_reviewed_tree_is_not_migrated_again(self):
        self.assertTrue(update.current_adapters_ready())
        with tempfile.TemporaryDirectory() as temporary,patch.object(update,'WORK',Path(temporary)),patch.object(update,'port_office',side_effect=AssertionError('Office adapters were replayed')),patch.object(update,'port_cad',side_effect=AssertionError('CAD adapter was replayed')),patch.object(update,'run') as command:
            update.prepare()
        self.assertEqual(command.call_count,1)
        self.assertIn('compileall',command.call_args.args[0])

if __name__=='__main__':unittest.main()
