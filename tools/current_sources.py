#!/usr/bin/env python3
"""Reproduce the November 9 Android adapters and build the requested products."""
from pathlib import Path
import argparse, copy, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, tomllib, zipfile

ROOT=Path(__file__).resolve().parents[1]
WORK=Path(os.environ.get('LUCY_BUILD_WORK', str(ROOT.parent/'lucy-build-work'))).resolve()
HEADS={'wordcraft':'05f781cfdac1d89034c0f4f5824b597ff845f2ef','pdfcraft':'ba28458ad8bd8d8b5b83c14f643bfa8ce9592f60','gridcraft':'e9addf52fe68847e6c1310fcfa5d42b7aa8b9650','deckcraft':'0623b430324cf4c3d1962e6ae7885cf30c011c5e','cadcraft':'a3d9348f63c2ad35391cc93980dc7ee7366f2ad6'}
OLD={'wordcraft':'729cd0a5fc953bbedbfdec4f6af18ad6d1780b3b','gridcraft':'6a8eb4ff42cfa88b5bdd3eec13c6db3874d95214','pdfcraft':'f42fda734243b66f54db87923d7c981d5221419e','deckcraft':'159ed07eb3f0522a5dc97d7cf1858242a6638659'}
sys.path.insert(0,str(ROOT))

def run(args,cwd=None,capture=False,check=True,env=None):
    return subprocess.run(list(map(str,args)),cwd=cwd,env=env,check=check,stdout=subprocess.PIPE if capture else None,stderr=subprocess.PIPE if capture else None,text=capture)

def git(folder,*args,check=True):
    return run(['git',*args],folder,True,check)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def edit(path,old,new):
    path=ROOT/path;text=path.read_text()
    if old not in text:raise ValueError('Expected edit missing: '+str(path))
    path.write_text(text.replace(old,new,1))

def conflicts(source,name,choices):
    p=source/name;text=p.read_text()
    matches=list(re.finditer(r'^<<<<<<< ours\n(.*?)^=======\n(.*?)^>>>>>>> theirs\n',text,re.M|re.S))
    if len(matches)!=len(choices):raise ValueError(('Unexpected source conflicts',name,len(matches)))
    for m,choose in reversed(list(zip(matches,choices))):
        text=text[:m.start()]+choose(m[1],m[2])+text[m.end():]
    p.write_text(text)

def port_office():
    from app import worker
    from app.core import pipeline
    worker.revision=lambda name,mode:HEADS[name]
    snapshot=worker.resolve(['wordcraft','gridcraft','pdfcraft','deckcraft'],'main','all')
    save(WORK/'snapshot.json',snapshot)
    manifest=ROOT/'engine/pipeline/compat/manifest.json'
    data=json.loads(manifest.read_text())
    compat=manifest.parent
    sources={}
    ours=lambda a,b:a
    theirs=lambda a,b:b
    for engine in snapshot['engine_lock']['engines']:
        name=engine['id'];folder=WORK/'office-review'/name
        try:pipeline.prepare_engine(snapshot,name,folder)
        except pipeline.BuildError as error:print('Reviewing adapter:',name,str(error),flush=True)
        source=folder/'sources'/name;sources[name]=source
        if name=='wordcraft':
            conflicts(source,'crates/ui-egui/src/backstage.rs',[theirs])
            conflicts(source,'crates/ui-egui/src/dialogs/dispatch.rs',[theirs])
            p=source/'crates/ui-egui/src/backstage.rs';s=p.read_text()
            start=s.index('/// The bottom of the backstage menu:');end=s.index('/// Draws the Backstage side menu',start)
            p.write_text(s[:start]+s[end:])
            p=source/'crates/ui-egui/src/tests.rs';s=p.read_text()
            start=s.index('/// The Options toggle hides the community pill');end=s.index('/// File › Options › Advanced › Editing:',start)
            p.write_text(s[:start]+s[end:])
        elif name=='pdfcraft':
            conflicts(source,'crates/ui-egui/src/app.rs',[lambda a,b:a.replace('QuickTool::Select','QuickTool::Hand'),lambda a,b:a+b,ours,ours])
            p=source/'crates/ui-egui/src/app.rs';p.write_text(p.read_text().replace('        chrome::tab_strip(self, ui);\n',''))
            conflicts(source,'crates/ui-egui/src/chrome.rs',[theirs,lambda a,b:a.replace('                    app.menu_bar_ui(ui);','                    ui.scope(|ui| {\n                        ui.style_mut().text_styles.insert(egui::TextStyle::Button, theme::regular(12.5));\n                        app.menu_bar_ui(ui);\n                    });')])
            conflicts(source,'crates/ui-egui/src/dialogs.rs',[lambda a,b:a.replace('pub(super) mod credits;\n','')])
            conflicts(source,'crates/ui-egui/src/lib.rs',[lambda a,b:a.replace('use dialogs::credits;\n','')+b])
            conflicts(source,'crates/ui-egui/src/widgets.rs',[theirs])
            p=source/'crates/ui-egui/src/home.rs';s=p.read_text()
            if 'pub fn show(' in s:raise ValueError('PDF Home source changed')
            p.write_text(s.replace('pub mod folders_ui;','pub mod folders_ui;\n\npub fn show(_app: &mut PdfCraftApp, ui: &mut egui::Ui) {\n    ui.centered_and_justified(|ui| { ui.label("Abre un PDF para comenzar"); });\n}\n',1))
        elif name=='deckcraft':
            p=source/'crates/ui-egui/src/dialogs.rs';s=p.read_text().replace('mod about;\n','').replace('pub mod credits;\n','').replace('pub use about::{about, paint_logo, version_line};\n','')
            p.write_text('\n'.join(line for line in s.split('\n') if '"about" => "About DeckCraft"' not in line))
            p=source/'crates/ui-egui/src/lib.rs';p.write_text(p.read_text().replace('pub use dialogs::credits;\n',''))
            p=source/'crates/ui-egui/src/dialogs/body.rs';s=p.read_text().replace('use super::about::{about, credits_block};\n','').replace('        "about" => dlg_about(app, ui, d),\n','')
            start=s.index('fn dlg_about(');end=s.index('fn dlg_autocorrect(',start);p.write_text(s[:start]+s[end:])
            p=source/'crates/ui-egui/src/backstage/files.rs';p.write_text(p.read_text().replace('        crate::dialogs::paint_logo(ui.painter(), r);','        ui.painter().text(r.center(), egui::Align2::CENTER_CENTER, "Lucy", crate::theme::font(22.0), crate::theme::Tokens::get(ui.ctx()).text);'))
        git(source,'add','--all')
        if git(source,'diff','--name-only','--diff-filter=U').stdout.strip():raise ValueError('Unresolved '+name)
        git(source,'diff','--check','HEAD')
        record=data['engines'][name];excludes=[':(exclude)'+p for p in record['source_prune']]
        patch=subprocess.check_output(['git','diff','--binary','HEAD','--','.',*excludes],cwd=source)
        rel=name+'/2026-11-09-all.patch';(compat/rel).write_bytes(patch)
        record.update(base_commit=HEADS[name],reviewed_at='2026-11-09')
        record['patches']['all']={'file':rel,'sha256':sha(compat/rel)}
    for name,source in sources.items():
        dest=WORK/'spanish-review'/name
        run(['git','clone','--quiet','--shared','--no-checkout',source,dest])
        git(dest,'fetch','--quiet','--depth=1','https://github.com/storytold/'+name+'.git',OLD[name])
        git(dest,'checkout','--quiet','--detach',OLD[name])
        git(dest,'apply','--index',str(compat/name/'2026-11-06-all.patch'))
        all_tree=git(dest,'write-tree').stdout.strip()
        git(dest,'reset','--hard','--quiet',OLD[name])
        git(dest,'apply','--index',str(compat/name/'2026-11-06-es.patch'))
        es_tree=git(dest,'write-tree').stdout.strip()
        overlay=WORK/(name+'-spanish.patch')
        overlay.write_bytes(subprocess.check_output(['git','diff','--binary',all_tree,es_tree],cwd=dest))
        git(dest,'reset','--hard','--quiet',HEADS[name])
        git(dest,'apply','--index',str(compat/data['engines'][name]['patches']['all']['file']))
        result=git(dest,'apply','--3way','--index',str(overlay),check=False)
        if result.returncode:
            if name=='gridcraft':
                conflicts(dest,'crates/ui-egui/src/theme/font_setup.rs',[lambda a,b:'    font_definitions_impl(crate::i18n::Language::Es, Vec::new(), false)\n'])
            elif name=='deckcraft':
                pending=git(dest,'diff','--name-only','--diff-filter=U').stdout.splitlines()
                if set(pending)!={'crates/ui-egui/src/dialogs.rs','crates/ui-egui/src/dialogs/body.rs'}:raise ValueError(result.stderr)
                for filename in pending:
                    p=dest/filename;content=p.read_text()
                    def spanish_dialog(match):
                        chosen=match[2]
                        if re.search(r'\b(?:dlg_about|credits_block)\b|super::about|mod about|pub use about|"about"\\s*=>',chosen):
                            raise ValueError('Obsolete About code in Spanish merge: '+filename)
                        return chosen
                    content,count=re.subn(r'^<<<<<<< ours\n(.*?)^=======\n(.*?)^>>>>>>> theirs\n',spanish_dialog,content,flags=re.M|re.S)
                    if not count:raise ValueError('Unexpected DeckCraft conflict format')
                    p.write_text(content)
            else:raise ValueError(result.stderr)
            git(dest,'add','--all')
        if git(dest,'diff','--name-only','--diff-filter=U').stdout.strip():raise ValueError('Spanish conflicts: '+name)
        excludes=[':(exclude)'+p for p in data['engines'][name]['source_prune']]
        patch=subprocess.check_output(['git','diff','--binary','HEAD','--','.',*excludes],cwd=dest)
        rel=name+'/2026-11-09-es.patch';(compat/rel).write_bytes(patch)
        data['engines'][name]['patches']['es']={'file':rel,'sha256':sha(compat/rel)}
    data['date']='2026-11-09';save(manifest,data)
    for p in compat.glob('*/2026-11-06-*.patch'):p.unlink()
    return snapshot

def port_cad():
    from app.core import pipeline
    sys.path.insert(0,str(ROOT/'native-cad'));import tablet
    kit=ROOT/'native-cad';base=WORK/'cad-review';base.mkdir(parents=True)
    raw=base/'raw';old='865fa9afb047e6a5053b8f51c3ad4feef90804d2';current=HEADS['cadcraft']
    pipeline.clone_commit('storytold/cadcraft',current,raw,old)
    reports={}
    for name,commit in [('previous',old),('current',current)]:
        archive=base/(name+'.zip')
        run(['git','archive','--format=zip','--prefix=cadcraft/','--output='+str(archive),commit],raw)
        reports[name]=tablet.prepare(archive,base/name,kit)
    if reports['previous']['conflicts']:raise ValueError(reports['previous']['conflicts'])
    a=json.loads((kit/'adapter.json').read_text())
    previous=next(p for p in a['source_profiles'] if p['id']=='main-865fa9af')
    names={p['path'] for p in a['modified']+a['owned']+previous['files']}
    ported=base/'ported';run(['git','clone','--quiet','--shared','--no-checkout',raw,ported]);git(ported,'checkout','--quiet','--detach',current)
    with tempfile.TemporaryDirectory(dir=base) as temporary:
        for name in sorted(names):
            old_port=base/'previous'/name
            if not old_port.is_file():continue
            old_raw=subprocess.run(['git','show',old+':'+name],cwd=raw,capture_output=True)
            target=old_port.read_bytes();path=ported/name
            if old_raw.returncode:
                if path.exists() and path.read_bytes()!=target:raise ValueError('New upstream owned path: '+name)
                merged=target
            else:
                if not path.is_file():raise ValueError('Upstream removed '+name)
                merged,ok=tablet.merge_one(path.read_bytes(),old_raw.stdout,target,Path(temporary))
                if not ok:raise ValueError('New CAD conflict: '+name)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(merged);path.chmod(old_port.stat().st_mode&0o777)
    match={}
    for name in set(previous['match'])|{r['path'] for r in a['modified']}|{'Cargo.lock','Cargo.toml'}:
        match[name]=hashlib.sha256(subprocess.check_output(['git','show',current+':'+name],cwd=raw)).hexdigest()
    conflicting={r['path'] for r in reports['current']['conflicts']}
    files=[]
    for p in sorted(ported.rglob('*')):
        if not p.is_file() or '.git' in p.relative_to(ported).parts:continue
        name=p.relative_to(ported).as_posix();other=base/'current'/name
        if name not in conflicting and (not other.exists() or other.read_bytes()==p.read_bytes()):continue
        rel='compat/main-a3d9348f/'+name;dest=kit/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        files.append({'path':name,'source':rel,'sha256':sha(dest),'mode':p.stat().st_mode&0o777})
    if not conflicting<={r['path'] for r in files}:raise ValueError('CAD conflicts not covered')
    a['adapter_version']='1.3.0-lucy'
    a['source_profiles'].append({'id':'main-a3d9348f','source_commit':current,'match':dict(sorted(match.items())),'files':files})
    save(kit/'adapter.json',a)
    print('CAD profile:',len(files),'outputs,',len(match),'input guards',flush=True)

PACKAGER=r"""
class RustEntries(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.entries=[]
        self.feed(html)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='link' and attrs.get('rel')=='rust':
            self.entries.append((self.get_starttag_text(),attrs))

def verified_download(url,expected,target,limit=64*1024*1024):
    if not url.startswith('https://') or not re.fullmatch('[a-f0-9]{64}',expected):
        raise ValueError('Unpinned resource')
    if target.is_file() and digest(target)==expected:return
    import time
    target.parent.mkdir(parents=True,exist_ok=True)
    part=target.with_name(target.name+'.part')
    try:
        for attempt in range(3):
            try:
                request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Lucy-Builder/2.3.0'})
                with urllib.request.urlopen(request,timeout=60) as response,part.open('wb') as output:
                    size=0
                    while chunk:=response.read(1024*1024):
                        size+=len(chunk)
                        if size>limit:raise ValueError('Resource exceeds size limit')
                        output.write(chunk)
                break
            except OSError:
                if attempt==2:raise
                time.sleep(2)
        if digest(part)!=expected:raise ValueError('Resource checksum mismatch: '+target.name)
        part.replace(target)
    finally:part.unlink(missing_ok=True)

def pdf_models(source,dist):
    import tomllib
    wanted={'text-detection.onnx','text-recognition.onnx'}
    records=[r for r in tomllib.loads((source/'ATTRIBUTION.toml').read_text())['fetched'] if r.get('file') in wanted]
    if {r['file'] for r in records}!=wanted:raise ValueError('Missing pinned OCR models')
    dest=dist/'models';dest.mkdir()
    for r in records:
        cache=ROOT/'.cache/models'/r['sha256']/r['file']
        verified_download(r['url'],r['sha256'],cache)
        shutil.copyfile(cache,dest/r['file'])
        license_name='LICENSE-'+r['licence_sha256'][:12]+'.txt';license_path=ROOT/'.cache/models'/license_name
        verified_download(r['licence_url'],r['licence_sha256'],license_path,1024*1024)
        shutil.copyfile(license_path,dest/license_name)
    (dest/'ATTRIBUTION.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')

def compile_binary(name,manifest,source,env,bindgen,dist):
    subprocess.run(['cargo','build','--locked','--release','--target','wasm32-unknown-unknown','--manifest-path',str(manifest),'--bin',name],cwd=source,env=env,check=True)
    raw=Path(env['CARGO_TARGET_DIR'])/'wasm32-unknown-unknown/release'/(name+'.wasm')
    subprocess.run([bindgen,'--target','web','--no-typescript','--weak-refs','--out-dir',str(dist),'--out-name',name,str(raw)],env=env,check=True)
    wasm=dist/(name+'_bg.wasm')
    if env.get('FOLIO_OPTIMIZE_WASM')=='1':
        optimizer=tool('wasm-opt','128');optimized=dist/(name+'_optimized.wasm')
        subprocess.run([optimizer,'-Oz','--all-features',str(wasm),'-o',str(optimized)],env={**env,'BINARYEN_CORES':'2'},check=True)
        optimized.replace(wasm)

def compile_editor(engine,source,env):
    import tomllib
    lock=tomllib.loads((source/'Cargo.lock').read_text())
    version=next(p['version'] for p in lock['package'] if p['name']=='wasm-bindgen')
    bindgen=tool('wasm-bindgen',version);name=engine['id']+'-web';page=source/f'apps/{name}/index.html'
    html=page.read_text();entries=RustEntries(html).entries;main=[e for e in entries if e[1].get('data-type')!='worker']
    if len(main)!=1:raise ValueError('Expected exactly one Rust WebAssembly entry point')
    dist=source/'dist/folio-android'
    if dist.exists():shutil.rmtree(dist)
    dist.mkdir(parents=True)
    compile_binary(name,f'apps/{name}/Cargo.toml',source,env,bindgen,dist)
    seen={name}
    for tag,attrs in entries:
        if attrs.get('data-type')!='worker':continue
        manifest=(page.parent/attrs.get('href','')).resolve()
        if not manifest.is_relative_to(source.resolve()) or manifest.name!='Cargo.toml':raise ValueError('Worker manifest outside the selected sources')
        worker=tomllib.loads(manifest.read_text())['package']['name']
        if not re.fullmatch('[a-z0-9][a-z0-9_-]*',worker) or worker in seen:raise ValueError('Invalid or duplicate worker')
        seen.add(worker);compile_binary(worker,manifest,source,env,bindgen,dist)
        glue=dist/(worker+'.js');wasm=dist/(worker+'_bg.wasm');stamp=hashlib.sha256(glue.read_bytes()+wasm.read_bytes()).hexdigest()[:16]
        stem=worker+'-'+stamp;text=glue.read_text();old=worker+'_bg.wasm'
        if text.count(old)!=1:raise ValueError('Unexpected worker loader')
        glue.write_text(text.replace(old,stem+'_bg.wasm'));glue.rename(dist/(stem+'.js'));wasm.rename(dist/(stem+'_bg.wasm'))
        loader=stem+'_loader.js';(dist/loader).write_text(f"import init from './{stem}.js';\nawait init();\n")
        if '</head>' not in html:raise ValueError('Worker page has no head')
        html=html.replace(tag,'',1).replace('</head>',f'<meta name="{worker}" content="./{loader}" />\n</head>',1)
        if worker=='pdfcraft-ocr-worker':pdf_models(source,dist)
    html=re.sub(r'<link\b[^>]*rel="icon"[^>]*>','',html)
    bootstrap=f'''<script type="module">\nimport init, * as bindings from './{name}.js';\nconst wasm = await init({{module_or_path:'./{name}_bg.wasm'}});\nwindow.wasmBindings = bindings;\ndispatchEvent(new CustomEvent("TrunkApplicationStarted", {{detail:{{wasm}}}}));\n</script>'''
    (dist/'index.html').write_text(html.replace(main[0][0],bootstrap,1))
"""

def refresh_builder(snapshot):
    for name in ['app/worker.py','app/host.py','app/native_cad.py','app/gui.py','build_flatpak.py','release_source.py','README.md']:
        p=ROOT/name;p.write_text(p.read_text().replace('2.2.0','2.3.0'))
    edit('release_source.py','(2026,11,6,0,0,0)','(2026,11,9,0,0,0)')
    edit('engine/pipeline/build_lucy.py',"engine['adapter_profile'] = '2026-11-06'","engine['adapter_profile'] = candidate.get('reviewed_at', '2026-11-06')")
    edit('engine/pipeline/build_lucy.py',
"""    result = subprocess.run(['git', 'apply', '--3way', '--index', str(patch)], cwd=source,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    reviewed = False
    if result.returncode:
        candidate = compatibility.profile(engine['id'], engine.get('language_mode', 'es'))""",
"""    candidate = compatibility.profile(engine['id'], engine.get('language_mode', 'es'))
    # An exact reviewed adapter takes priority: a clean old merge can still use removed APIs.
    exact_reviewed = candidate is not None and candidate['base_commit'] == engine['source_commit']
    result = None if exact_reviewed else subprocess.run(
        ['git', 'apply', '--3way', '--index', str(patch)], cwd=source,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    reviewed = False
    if exact_reviewed or result.returncode:""")
    p=ROOT/'engine/pipeline/lucy/scripts/build_engines.py';s=p.read_text().replace('import argparse\n','import argparse\nfrom html.parser import HTMLParser\n',1)
    start=s.index('def compile_editor(');end=s.index('\ndef digest(',start)
    s=s[:start]+PACKAGER+'\n'+s[end:]
    s=s.replace('if relative.as_posix() != "index.html" and path.suffix not in {".wasm", ".js"}:',
"""model_asset = relative.parts[0] == 'models' and path.suffix in {'.onnx', '.txt', '.json'}
        if relative.as_posix() != "index.html" and path.suffix not in {".wasm", ".js"} and not model_asset:""")
    p.write_text(s)
    edit('engine/pipeline/build_lucy.py',"    cargo_notices(source, name, output / 'notices', env)",
"""    cargo_notices(source, name, output / 'notices', env)
    models = output / 'engine/models'
    if models.is_dir():
        for path in sorted(models.iterdir()):
            if path.suffix in {'.txt', '.json'}:
                target = output / 'notices/pdfcraft-ocr-models' / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)""")
    edit('native-cad/tablet.py','def run_logged(command: list[str], root: Path, env: dict, log: Path) -> None:','def run_logged(command: list[str], root: Path, env: dict, log: Path, *, discard_stdout: bool = False) -> None:')
    edit('native-cad/tablet.py',
'with subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,',
'with subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.DEVNULL if discard_stdout else subprocess.PIPE, stderr=subprocess.PIPE if discard_stdout else subprocess.STDOUT,')
    edit('native-cad/tablet.py','for line in child.stdout:','for line in (child.stderr if discard_stdout else child.stdout):')
    edit('native-cad/tablet.py','run_logged(["cargo", "metadata", "--format-version", "1"], root, env, log)','run_logged(["cargo", "metadata", "--format-version", "1"], root, env, log, discard_stdout=True)')
    p=ROOT/'native-cad/tests/test_adapter.py';p.write_text(p.read_text().replace('def minimal_resolution(*args):','def minimal_resolution(*args, **kwargs):').replace('def invalid_resolution(*args):','def invalid_resolution(*args, **kwargs):'))
    p=ROOT/'app/revisions.py';p.write_text("""MODES=('reviewed','verified','release','main')
LABELS=('Revisadas · 09/11/2026','Versiones base anteriores','Última versión publicada','Desarrollo · main de GitHub')
def selected_index(settings):
    if 'revision_mode' not in settings:return 0
    value=settings['revision_mode']
    if type(value) is not int:return 0
    schema=settings.get('revision_schema')
    if schema==3:return value if 0<=value<len(MODES) else 0
    if schema==2:return value+1 if 0<=value<3 else 0
    return 3 if value==0 else 1
""")
    p=ROOT/'app/worker.py';s=p.read_text().replace('from .catalog import BY_ID,OFFICE,selection','from .catalog import BY_ID,OFFICE,selection\nfrom .revisions import MODES',1)
    s=s.replace("if mode=='verified':","if mode in {'reviewed','verified'}:")
    s=s.replace("ROOT/'app/verified.json'","ROOT/'app'/('reviewed.json' if mode=='reviewed' else 'verified.json')")
    s=s.replace("not in {'main','verified','release'}","not in MODES")
    s=s.replace("'version_name':'2.0.'+time.strftime","'version_name':VERSION+'.'+time.strftime")
    s=s.replace('finally:os.environ.clear();os.environ.update(old_env)','finally:os.environ.clear();os.environ.update(old_env);lock.close()')
    p.write_text(s)
    p=ROOT/'app/gui.py';s=p.read_text().replace('from .catalog import APPS,BY_ID,OFFICE','from .catalog import APPS,BY_ID,OFFICE\nfrom .revisions import MODES,LABELS,selected_index',1)
    start=s.index('self.revisions=Gtk.DropDown.new_from_strings(');end=s.index(';left.append(self.revisions)',start)
    s=s[:start]+'self.revisions=Gtk.DropDown.new_from_strings(list(LABELS));self.revisions.set_selected(selected_index(self.settings))'+s[end:]
    s=s.replace("'revision_schema':2","'revision_schema':3").replace("'revision_mode':['verified','release','main'][self.revisions.get_selected()]","'revision_mode':MODES[self.revisions.get_selected()]")
    s=s.replace('Las versiones base quedan fijadas por commit y permiten volver atrás.','Las revisadas fijan las fuentes actuales de los cuatro editores y CADCraft. El resto conserva sus referencias base. Las versiones anteriores siguen disponibles.')
    p.write_text(s)
    old=json.loads((ROOT/'app/verified.json').read_text());old['heads'].update(HEADS);old['baseline_date']='2026-11-09';old['fonts']=snapshot['engine_lock']['fonts'];old['translations']=snapshot['engine_lock']['translations'];old['validated_apps']=list(HEADS)
    old['versions'].update(wordcraft='0.15.1',pdfcraft='0.18.1',gridcraft='0.16.0',deckcraft='0.15.0',cadcraft='0.17.0');save(ROOT/'app/reviewed.json',old)
    p=ROOT/'app/web.py';s=p.read_text().replace("Path(__file__).parents[1]/'app/verified.json'","Path(__file__).parents[1]/'app'/('reviewed.json' if job['revision_mode']=='reviewed' else 'verified.json')").replace("if job['revision_mode']=='verified' else pipeline.latest","if job['revision_mode'] in {'reviewed','verified'} else pipeline.latest");p.write_text(s)
    p=ROOT/'flatpak/io.github.pedroguille.LucyBuilder.metainfo.xml';s=p.read_text().replace('<releases>','<releases><release version="2.3.0" date="2026-11-09"><description><p>Pin current sources with a separate older fallback; refresh all five Android adapters and package the new PDF OCR worker and offline models.</p></description></release>',1);p.write_text(s)
    p=ROOT/'README.md';s=p.read_text().replace('revisadas el 6 de noviembre de 2026','revisadas el 9 de noviembre de 2026').replace('Elegí **Desarrollo · main de GitHub** para descargarlas. **Versiones base guardadas** conserva las revisiones anteriores.','Elegí **Revisadas · 09/11/2026** para reproducir esta entrega. Se conservan las versiones base anteriores, las publicaciones y main.').replace('El constructor prueba primero el adaptador anterior y, si hay conflictos, el adaptador revisado;','Una revisión exacta usa su adaptador revisado. Otras fuentes prueban la integración anterior y después la revisada;');p.write_text(s)
    p=ROOT/'tests/integration_package.py';s=p.read_text().replace("assert len([n for n in archive.namelist() if n.endswith('.wasm')])==len(ids)","assert all('assets/engines/'+name+'/'+name+'-web_bg.wasm' in archive.namelist() for name in ids)");p.write_text(s)
    p=ROOT/'flatpak/io.github.pedroguille.LucyBuilder.json';p.write_text(p.read_text().replace('README.md LICENSE /app/lib/lucy-builder/','README.md LICENSE VALIDACION-2.3.0.md /app/lib/lucy-builder/'))
    kit=ROOT/'native-cad';blocked={'__pycache__','.git','cache','work','dist','private','target'}
    lines=[sha(p)+'  '+p.relative_to(kit).as_posix() for p in sorted(kit.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='CONTENTS.sha256' and not set(p.relative_to(kit).parts)&blocked and p.suffix not in {'.pyc','.p12','.pfx','.jks','.keystore','.apk'}]
    (kit/'CONTENTS.sha256').write_text('\n'.join(lines)+'\n')

def prepare():
    WORK.mkdir(parents=True,exist_ok=True)
    snapshot=port_office();port_cad();refresh_builder(snapshot)
    (ROOT/'VALIDACION-2.3.0.md').write_text('# Validación 2.3.0\n\nFuentes fijadas el 9 de noviembre de 2026. La compilación y las verificaciones se registran en el workflow de esta entrega.\n')
    run([sys.executable,'-m','compileall','-q','app','engine','native-cad'],ROOT)
    print('Prepared current office and native CAD adapters.',flush=True)

def build():
    from app import worker
    state=WORK/'compiler';dest=ROOT/'deliverables';dest.mkdir(exist_ok=True)
    for mode,ids in [('individual',['cadcraft']),('lucy',['wordcraft','pdfcraft','gridcraft']),('individual',['deckcraft'])]:
        print('BUILD',mode,ids,flush=True)
        worker.run({'mode':mode,'apps':ids,'output':str(WORK/'products'),'jobs':2,'revision_mode':'reviewed','language_mode':'all','accept_sdk_license':True},state)
        if ids==['deckcraft']:continue
        product='cadcraft' if mode=='individual' else 'lucy'
        folder=max((WORK/'products'/product).glob('*/build-info.json'),key=lambda p:p.stat().st_mtime).parent
        info=json.loads((folder/'build-info.json').read_text());apk=folder/('CADCraft.apk' if product=='cadcraft' else 'Lucy.apk')
        if sha(apk)!=info['apk_sha256']:raise ValueError('Published APK digest differs')
        if set(info['heads'])!=set(ids) or any(info['heads'][n]!=HEADS[n] for n in ids):raise ValueError('Wrong APK source selection')
        if mode=='lucy':
            with zipfile.ZipFile(apk) as z:
                selection=json.loads(z.read('assets/selection.json'))
                if set(selection['engines'])!=set(ids):raise ValueError('Unexpected Lucy engines')
                if any(n.startswith('assets/engines/deckcraft/') for n in z.namelist()):raise ValueError('DeckCraft entered Lucy')
                if not any(n.startswith('assets/engines/pdfcraft/models/') and n.endswith('.onnx') for n in z.namelist()):raise ValueError('OCR models missing')
                if not any('pdfcraft-ocr-worker-' in n and n.endswith('.wasm') for n in z.namelist()):raise ValueError('OCR worker missing')
        name='CADCraft-Tablet-0.17.0-arm64-v8a.apk' if mode=='individual' else 'Lucy-WordCraft-PDFcraft-GridCraft.apk'
        shutil.copyfile(apk,dest/name)
        save(dest/(product+'-build-info.json'),{k:v for k,v in info.items() if k not in {'apk','source','report','output'}})
    print('Both requested APKs are signed and verified; DeckCraft release build validated separately.',flush=True)

def package():
    dest=ROOT/'deliverables';run([sys.executable,'build_flatpak.py','--output',dest],ROOT)
    table='\n'.join('| '+n+' | '+h+' |' for n,h in HEADS.items())
    (ROOT/'VALIDACION-2.3.0.md').write_text('# Validación de Lucy Builder 2.3.0\n\n## Fuentes\n\n| App | Commit |\n| --- | --- |\n'+table+'\n\n## Comprobaciones\n\n- Pruebas Python y regresión JavaScript del constructor.\n- Compilaciones release: CADCraft ARM64 nativo y los cuatro motores WebAssembly.\n- APK de Lucy con WordCraft, PDFcraft y GridCraft; se verifica que DeckCraft no esté incluido.\n- PDFcraft incluye su worker OCR, modelos ONNX verificados por SHA-256, licencia y atribuciones.\n- APK de CADCraft con firma verificada y soporte de páginas nativas de 16 KiB.\n- Flatpak creado con las herramientas oficiales.\n\nNo se probaron en un dispositivo físico ni se recompilaron las otras diez aplicaciones del catálogo. Las versiones anteriores siguen disponibles. Cambios posteriores de main pueden necesitar adaptar las fuentes otra vez.\n')
    # Repack with the completed validation record.
    run([sys.executable,'build_flatpak.py','--output',dest],ROOT)
    names=['Lucy-Builder-2.3.0-x86_64.flatpak','CADCraft-Tablet-0.17.0-arm64-v8a.apk','Lucy-WordCraft-PDFcraft-GridCraft.apk']
    (dest/'SHA256SUMS.txt').write_text(''.join(sha(dest/n)+'  '+n+'\n' for n in names))
    run(['git','add','app','engine','native-cad','tests','flatpak','README.md','build_flatpak.py','release_source.py','VALIDACION-2.3.0.md'],ROOT)
    git(ROOT,'diff','--cached','--check')
    patch=subprocess.check_output(['git','diff','--cached','--binary','HEAD'],cwd=ROOT)
    (dest/'constructor-source-update.patch').write_bytes(patch)
    print('Ready:',names,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','build','package']);args=parser.parse_args()
    {'prepare':prepare,'build':build,'package':package}[args.stage]()
