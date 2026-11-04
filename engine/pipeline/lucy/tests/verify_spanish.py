"""Audit current Spanish UI catalogs; browser locale/migration QA is in spanish.cjs."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
options = parser.parse_args()
lock = json.loads((root / 'engine-lock.json').read_text())
assert lock['ui_languages'] == ['es']


def values(text, suffix):
    if suffix == '.tsv':
        return [line.split('\t')[-1] for line in text.splitlines() if '\t' in line and not line.startswith('#')]
    result = []
    literal = r'"(?:[^"\\]|\\.)*"'
    pattern = r'=>\s*(' + literal + r')|\(\s*' + literal + r'\s*,\s*(' + literal + r')'
    for match in re.finditer(pattern, text):
        try:
            result.append(json.loads(match[1] or match[2]))
        except ValueError:
            pass
    return result


pruned = 0
for engine in lock['engines']:
    name = engine['id']
    source = options.source_root / name
    installed = root / 'app/src/main/assets/engines' / name
    manifest = json.loads((installed / 'folio-engine.json').read_text())
    assert manifest['ui_languages'] == ['es']
    assert manifest['ui_translations'] == lock['translations']
    assert manifest['source_prune'] == engine.get('source_prune', [])
    assert re.search(r'<html[^>]*lang="es"', (installed / 'index.html').read_text())
    for filename in engine.get('source_prune', []):
        assert not (source / filename).exists(), filename
        pruned += 1
    ui = source / 'crates/ui-egui/src'
    if name == 'deckcraft':
        assert (ui / 'spanish.rs').is_file()
        print('PASS: deckcraft uses the Spanish UI dictionary')
        continue
    facade = (ui / 'i18n.rs').read_text()
    if name == 'gridcraft':
        assert re.search(r'pub enum Language\s*\{\s*#\[default\]\s*Es,\s*\}', facade)
        assert re.search(r'pub const ALL:\s*\[Self; 1\]', facade)
    else:
        assert re.search(r'pub static LANGUAGES:\s*\[LangInfo; 1\]', facade)
        assert 'pub struct Lang;' in facade
    wasm = next(installed.glob('*.wasm')).read_bytes()
    spanish_path = ui / ('i18n/es.rs' if name == 'gridcraft' else 'i18n/es.tsv')
    spanish = set(values(spanish_path.read_text(), spanish_path.suffix)) if spanish_path.exists() else set()
    checked = 0
    for filename in engine.get('source_prune', []):
        if not any('/' + code in filename for code in ['de.', 'fr.', 'ja.', 'zh-hans.']):
            continue
        original = subprocess.check_output(['git', 'show', 'HEAD:' + filename], cwd=source, text=True)
        candidates = [v for v in values(original, Path(filename).suffix)
                      if 40 < len(v.encode()) < 320 and v not in spanish]
        assert len(candidates) >= 3, (name, filename)
        # Examine all candidates, rather than choosing only absent witnesses.
        remaining = [v for v in candidates if v.encode() in wasm]
        assert not remaining, (name, filename, remaining[:3])
        checked += len(candidates)
    if name != 'wordcraft':
        assert checked >= 12, (name, checked)
    print(f'PASS: {name}, singleton Spanish UI; {checked} foreign catalog phrases absent')

spec = lock['translations']
assert set(spec['files']) == {'locales/es/common.tsv', 'locales/es/wordcraft.tsv'}
for filename, expected in spec['files'].items():
    assert hashlib.sha256((root / '.cache/spanish-i18n' / filename).read_bytes()).hexdigest() == expected
for folder in ['spanish-i18n', 'spanish-i18n-build']:
    locales = root / '.cache' / folder / 'locales'
    assert {path.name for path in locales.iterdir() if path.is_dir()} == {'es'}
supplement = (root / spec['supplement']).read_bytes()
assert hashlib.sha256(supplement).hexdigest() == spec['supplement_sha256']
assert (root / '.cache/spanish-i18n-build/locales/es/wordcraft.tsv').read_bytes() == (root / '.cache/spanish-i18n/locales/es/wordcraft.tsv').read_bytes() + b'\n' + supplement
assert 'if code != "es"' in (options.source_root / 'wordcraft/crates/ui-egui/build.rs').read_text()
host = (root / 'app/src/main/assets/shell.js').read_text()
assert 'navigator.language' not in host and 'const translations' not in host
assert re.search(r'<html[^>]*lang="es"', (root / 'app/src/main/assets/index.html').read_text())
print(f'PASS: {pruned} retired UI/brand files pruned; shared Word input contains only pinned Spanish catalogs')
