"""Reviewed adapters for newer upstream layouts; old bases remain reproducible."""
from pathlib import Path
import hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parent/'compat'

def profile(name, language='all'):
    path=ROOT/'manifest.json'
    if not path.is_file():return None
    data=json.loads(path.read_text())
    record=data.get('engines',{}).get(name)
    if record is None:return None
    selected=record['patches'][language]
    patch=(ROOT/selected['file']).resolve()
    if not patch.is_relative_to(ROOT.resolve()) or not patch.is_file():
        raise ValueError('Ruta de adaptador incompatible: '+name)
    raw=patch.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=selected['sha256']:
        raise ValueError('El adaptador revisado cambió sin actualizar su hash: '+name)
    if not re.fullmatch('[a-f0-9]{40}',record['base_commit']):
        raise ValueError('Revisión de adaptador inválida: '+name)
    return {**record,'path':patch,'sha256':selected['sha256']}

def digest(name):
    records=[profile(name,mode) for mode in ('all','es')]
    return hashlib.sha256(json.dumps([{k:str(v) for k,v in r.items() if k!='path'} for r in records if r],sort_keys=True).encode()).hexdigest()

def spanish_only(source,name):
    """Keep upstream translation APIs; restrict catalogs without stale source copies."""
    build=source/'crates/ui-egui/build.rs'
    if name in {'wordcraft','pdfcraft'}:
        text=build.read_text()
        marker='    for (code, shared, app) in entries {'
        if marker not in text:raise ValueError('Cambió la integración de idiomas de '+name)
        build.write_text(text.replace(marker,marker+'\n        if code != "es" { continue; }',1))
    if name in {'wordcraft','pdfcraft'}:
        p=source/'crates/ui-egui/src/app.rs';text=p.read_text()
        marker='        if let Some(dark) = crate::folio::dark() {'
        setting='self.ui.language' if name=='wordcraft' else 'self.language'
        if marker not in text:raise ValueError('Cambió el puente de apariencia de '+name)
        p.write_text(text.replace(marker, '        '+setting+' = \"es\".into();\n'+marker,1))
    if name in {'wordcraft','pdfcraft'}:
        for path in (source/'crates/ui-egui/src').rglob('*.rs'):
            text=path.read_text();updated=text.replace('Lang::ES', 'Lang::from_pref(\"es\")')
            if updated != text:path.write_text(updated)
    if name=='gridcraft':
        p=source/'crates/ui-egui/src/i18n.rs';text=p.read_text()
        # Preserve enum variants and the public API used by workbook formula names,
        # but do not compile foreign UI catalog modules into this profile.
        foreign=re.findall(r'^mod (\w+);$',text,re.M)
        foreign=[code for code in foreign if code not in {'es','es_functions'}]
        for code in foreign:
            text=text.replace('mod '+code+';','')
            text=re.sub(r'\b'+re.escape(code)+r'::translate\(', 'es::translate(',text)
        p.write_text(text.replace('Self::En => None,', 'Self::En => es::translate(text),'))
