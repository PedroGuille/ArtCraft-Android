#!/usr/bin/env python3
"""Independent Lucy adapter: current upstream sources -> unsigned Android APK.

No signing key or GitHub credential is needed by this build. Signing is local
inside the Android constructor. A failed source merge never falls back to an old
compiled editor. Inputs identify immutable Git commits, never shell fragments.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TEMPLATE = HERE / 'lucy'
REPOS = {name: 'storytold/' + name for name in ('wordcraft', 'gridcraft', 'deckcraft', 'pdfcraft')}
SHA = re.compile(r'[a-f0-9]{40}')
REQUEST = re.compile(r'[a-f0-9]{32}')


class BuildError(Exception):
    pass


def run(argv, cwd=None, capture=False):
    return subprocess.run(list(map(str, argv)), cwd=cwd, check=True,
                          stdout=subprocess.PIPE if capture else None,
                          text=capture).stdout


def hash_file(path):
    with Path(path).open('rb') as src:
        return hashlib.file_digest(src, 'sha256').hexdigest()


def json_file(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def get(url, limit=8 * 1024 * 1024):
    if not url.startswith(('https://raw.githubusercontent.com/storytold/', 'https://api.github.com/repos/storytold/', 'https://api.github.com/repos/tangency-labs/')):
        raise BuildError('Origen de descarga no permitido')
    request = urllib.request.Request(url, headers={'User-Agent': 'Lucy-Constructor/0.1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise BuildError('La descarga supera el límite previsto')
    return data


def validate_heads(value):
    if not isinstance(value, dict) or set(value) != set(REPOS):
        raise BuildError('Se necesitan exactamente los cuatro proyectos de Lucy')
    if any(not isinstance(v, str) or not SHA.fullmatch(v) for v in value.values()):
        raise BuildError('Una revisión de Git no es válida')
    return value


def latest(repo):
    # No credentials: upstream source and font repositories are public.
    output = run(['git', 'ls-remote', 'https://github.com/' + repo + '.git', 'refs/heads/main'], capture=True)
    value = output.split()[0] if output.split() else ''
    if not SHA.fullmatch(value):
        raise BuildError('No se pudo resolver main: ' + repo)
    return value


def resolve_snapshot(heads, request_id, run_number):
    validate_heads(heads)
    if not REQUEST.fullmatch(request_id):
        raise BuildError('Identificador de compilación no válido')
    if not str(run_number).isdigit() or not 1 <= int(run_number) <= 2_000_000_000:
        raise BuildError('Número de compilación no válido')
    lock = json.loads((TEMPLATE / 'engine-lock.json').read_text())
    for engine in lock['engines']:
        engine['adapter_base_commit'] = engine['source_commit']
        engine['source_commit'] = heads[engine['id']]
        engine['source_branch'] = 'main'
        engine.pop('source_date', None)
    lock['fonts']['source_commit'] = latest('storytold/craft-fonts')
    rev = get('https://raw.githubusercontent.com/storytold/wordcraft/' + heads['wordcraft'] + '/craft-i18n.rev').decode().strip()
    if not SHA.fullmatch(rev):
        raise BuildError('Word no especifica una revisión compatible de craft-i18n')
    lock['translations']['source_commit'] = rev
    for name in lock['translations']['files']:
        if not name.startswith('locales/es/'):
            raise BuildError('Solo se admiten catálogos españoles')
        content = get('https://raw.githubusercontent.com/storytold/craft-i18n/' + rev + '/' + name)
        lock['translations']['files'][name] = hashlib.sha256(content).hexdigest()
    return {'schema': 1, 'request_id': request_id, 'heads': heads, 'engine_lock': lock,
            'version_name': '0.11.' + str(run_number), 'version_code': int(time.time() // 60),
            'adapter_version': 1, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


def clone_commit(repo, commit, folder, extra_commit=None):
    if not SHA.fullmatch(commit) or (extra_commit is not None and not SHA.fullmatch(extra_commit)):
        raise BuildError('Revisión no válida')
    folder.mkdir(parents=True)
    run(['git', 'init', '--quiet'], folder)
    run(['git', 'remote', 'add', 'origin', 'https://github.com/' + repo + '.git'], folder)
    refs = list(dict.fromkeys([commit] + ([extra_commit] if extra_commit else [])))
    run(['git', 'fetch', '--quiet', '--depth=1', 'origin', *refs], folder)
    run(['git', 'checkout', '--quiet', '--detach', commit], folder)


def apply_adapter(engine, project, sources):
    name = engine['id'];source = sources / name
    import compatibility
    clone_commit(REPOS[name], engine['source_commit'], source, engine['adapter_base_commit'])
    patch = project / 'third_party/patches' / (name + '.patch')
    multilingual = engine.get('language_mode') == 'all'
    if multilingual and name == 'deckcraft':
        import languages
        languages.deck_patch(patch)
    if multilingual:
        engine['source_prune'] = [p for p in engine.get('source_prune', []) if '/i18n/' not in p]
        if name == 'deckcraft':engine['source_prune'] = []
    # git can reconstruct each baseline blob from the fetched base commit. With
    # --3way it preserves non-overlapping upstream edits; conflicts stop the job.
    candidate = compatibility.profile(engine['id'], engine.get('language_mode', 'es'))
    # An exact reviewed adapter takes priority: a clean old merge can still use removed APIs.
    exact_reviewed = candidate is not None and candidate['base_commit'] == engine['source_commit']
    result = None if exact_reviewed else subprocess.run(
        ['git', 'apply', '--3way', '--index', str(patch)], cwd=source,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    reviewed = False
    if exact_reviewed or result.returncode:
        if candidate is not None:
            # A failed merge only touched this new, builder-owned checkout. Reset
            # it before trying the separately reviewed adapter; never build markers.
            run(['git', 'reset', '--hard', '--quiet', 'HEAD'], source)
            extras = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=source)
            for item in extras.split(b'\0'):
                if not item:continue
                relative = Path(os.fsdecode(item))
                if relative.is_absolute() or '..' in relative.parts:raise BuildError('Ruta temporal inválida')
                (source / relative).unlink(missing_ok=True)
            base = candidate['base_commit']
            if subprocess.run(['git', 'cat-file', '-e', base + '^{commit}'], cwd=source, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                run(['git', 'fetch', '--quiet', '--depth=1', 'origin', base], source)
            result = subprocess.run(['git', 'apply', '--3way', '--index', str(candidate['path'])], cwd=source,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode == 0:
                reviewed = True
                engine['adapter_base_commit'] = base
                engine['adapter_profile'] = candidate.get('reviewed_at', '2026-11-06')
                engine['source_prune'] = list(candidate['source_prune'])
                if engine.get('language_mode', 'es') == 'es':
                    compatibility.spanish_only(source, engine['id'])
    if result.returncode:
        conflicts = run(['git', 'diff', '--name-only', '--diff-filter=U'], source, capture=True).strip()
        raise BuildError(engine['id'] + ': la versión nueva requiere actualizar el adaptador.\n' +
                         (conflicts or result.stdout[-12000:]))
    root = source.resolve()
    for name in engine.get('source_prune', []):
        p = source / name
        if Path(name).is_absolute() or '..' in Path(name).parts or not p.resolve().is_relative_to(root):
            raise BuildError('Ruta de eliminación inválida')
        p.unlink(missing_ok=True)
    # Include newly added foreign catalogs too; document-language/font support
    # lives outside this UI-catalog folder and is deliberately retained.
    ui_catalogs = source / 'crates/ui-egui/src/i18n'
    prune = set(engine.get('source_prune', []))
    if not multilingual and engine['id'] in {'gridcraft', 'pdfcraft'}:
        for p in ui_catalogs.iterdir():
            if re.fullmatch(r'[a-z]{2,3}(?:-[a-z]{2,5})?\.(?:tsv|rs)', p.name) and p.stem not in {'es', 'mod', 'rtl', 'sys', 'lib'}:
                p.unlink();prune.add(p.relative_to(source).as_posix())
    if multilingual and not reviewed:
        import languages
        languages.restore(source, engine['id'])
    engine['source_prune'] = sorted(prune)
    excludes = [':(exclude)' + p for p in engine['source_prune']]
    patch.write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD', '--', '.', *excludes], cwd=source))
    rev_file = source / 'craft-i18n.rev'
    if reviewed and rev_file.is_file():
        rev = rev_file.read_text().strip()
        if not SHA.fullmatch(rev):raise BuildError('Revisión de idiomas inválida')
        engine['translations'] = {'repository':'storytold/craft-i18n', 'source_commit':rev}
    engine['version'] = tomllib.loads((source / 'Cargo.toml').read_text())['workspace']['package']['version']
    run(['git', 'diff', '--check', 'HEAD'], source)
    return source


def copy_notices(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name in ['LICENSE', 'LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'ATTRIBUTION.md', 'ATTRIBUTION.toml']:
        if (source / name).is_file():
            shutil.copyfile(source / name, destination / name)




def copy_template(destination):
    def ignore(folder, names):
        skip = {n for n in names if n in {'.cache', '.git', 'build', 'dist', '__pycache__', 'node_modules', '.gradle'}
                or Path(n).suffix in {'.apk', '.jks', '.keystore', '.p12', '.pfx', '.pyc'}}
        if Path(folder).resolve() == (TEMPLATE / 'app/src/main/assets').resolve():skip.add('engines')
        return skip
    shutil.copytree(TEMPLATE, destination, ignore=ignore)


def is_notice(path):
    name = path.name.upper()
    return path.suffix.lower() in {'', '.txt', '.md'} and any(
        name.startswith(prefix) for prefix in ['LICENSE', 'LICENCE', 'NOTICE', 'COPYING', 'COPYRIGHT', 'OFL'])


def copy_notice_tree(source, destination):
    copy_notices(source, destination)
    for current, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in {'.git', 'target', 'build', '.cache', 'dist', 'node_modules'}]
        for filename in files:
            p = Path(current) / filename
            if is_notice(p) and not p.is_symlink() and p.stat().st_size <= 2 * 1024 * 1024:
                target = destination / p.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True);shutil.copyfile(p, target)


def cargo_notices(source, name, output, env):
    result = subprocess.check_output(['cargo', 'metadata', '--locked', '--format-version', '1',
        '--filter-platform', 'wasm32-unknown-unknown', '--manifest-path', 'apps/' + name + '-web/Cargo.toml'],
        cwd=source, env=env, text=True)
    metadata = json.loads(result)
    packages = {p['id']: p for p in metadata['packages']}
    graph = {n['id']: [d['pkg'] for d in n['deps']] for n in metadata['resolve']['nodes']}
    entry = next(p['id'] for p in metadata['packages'] if p['name'] == name + '-web')
    pending, seen, rows = [entry], set(), []
    while pending:
        identity = pending.pop()
        if identity in seen:continue
        seen.add(identity);pending.extend(graph.get(identity, []))
        package = packages[identity]
        if not package.get('source'):continue
        folder = Path(package['manifest_path']).parent
        slug = package['name'] + '-' + package['version'] + '-' + hashlib.sha256(identity.encode()).hexdigest()[:8]
        if not re.fullmatch('[A-Za-z0-9_.+-]+', slug):raise BuildError('Identificador de dependencia no válido')
        destination = output / 'cargo' / slug
        for parent in [folder, *list(folder.parents)[:4]]:
            for license_file in parent.iterdir():
                if license_file.is_file() and not license_file.is_symlink() and is_notice(license_file):
                    destination.mkdir(parents=True, exist_ok=True)
                    target = destination / license_file.name
                    if target.exists() and target.read_bytes() != license_file.read_bytes():
                        target = destination / ('workspace-' + license_file.name)
                    shutil.copyfile(license_file, target)
            if (parent / '.git').exists():break
        explicit = package.get('license_file')
        if explicit:
            f = (folder / explicit).resolve()
            # Only conventional public license files, never arbitrary build-host files.
            if f.is_file() and is_notice(f) and f.stat().st_size <= 2 * 1024 * 1024 and f.is_relative_to(Path(env.get('CARGO_HOME', Path.home() / '.cargo')).resolve()):
                destination.mkdir(parents=True, exist_ok=True);shutil.copyfile(f, destination / f.name)
        rows.append({key: package.get(key) for key in ['name', 'version', 'source', 'license']})
    json_file(output / ('cargo-' + name + '.json'), sorted(rows, key=lambda row: (row['name'], row['version'], row['source'])))


def prepare_engine(snapshot, name, work):
    if name not in REPOS:
        raise BuildError('Editor desconocido')
    project = work / 'lucy';sources = work / 'sources'
    copy_template(project)
    lock = snapshot['engine_lock']
    engine = next(e for e in lock['engines'] if e['id'] == name)
    source = apply_adapter(engine, project, sources)
    json_file(project / 'engine-lock.json', lock)
    return source


def compile_engine(snapshot, name, work, cargo_target=None):
    prepare_engine(snapshot, name, work)
    return compile_prepared(snapshot, name, work, cargo_target)


def compile_prepared(snapshot, name, work, cargo_target=None):
    project = work / 'lucy';sources = work / 'sources';source = sources / name
    lock = snapshot['engine_lock']
    engine = next(e for e in lock['engines'] if e['id'] == name)
    json_file(project / 'engine-lock.json', lock)
    env = dict(os.environ)
    env.setdefault('CARGO_BUILD_JOBS', '2')
    env['CARGO_TARGET_DIR'] = str((cargo_target or work / 'target').resolve())
    # The installed manifest records the actual user build's version.
    builder = project / 'scripts/build_engines.py'
    text = (TEMPLATE / "scripts/build_engines.py").read_text().replace('"folio_version": "0.10.0"', '"folio_version": ' + repr(snapshot['version_name']))
    builder.write_text(text)
    subprocess.run([sys.executable, str(builder), '--engine', name, '--source-root', str(sources.resolve())],
                   cwd=project, env=env, check=True)
    output = work / 'output';output.mkdir()
    shutil.copytree(project / 'app/src/main/assets/engines' / name, output / 'engine')
    shutil.copyfile(project / 'third_party/patches' / (name + '.patch'), output / 'adapter.patch')
    json_file(output / 'engine.json', engine)
    copy_notice_tree(source, output / 'notices' / name)
    cargo_notices(source, name, output / 'notices', env)
    models = output / 'engine/models'
    if models.is_dir():
        for path in sorted(models.iterdir()):
            if path.suffix in {'.txt', '.json'}:
                target = output / 'notices/pdfcraft-ocr-models' / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    fonts = sources / 'craft-fonts'
    copy_notices(fonts, output / 'notices/craft-fonts')
    for p in fonts.rglob('*'):
        if p.is_file() and any(s in p.name.lower() for s in ['license', 'licence', 'ofl', 'copyright']) and p.suffix.lower() in {'.md', '.txt', ''}:
            target = output / 'notices/craft-fonts' / p.relative_to(fonts)
            target.parent.mkdir(parents=True, exist_ok=True);shutil.copyfile(p, target)
    # Preserve the current shared catalog's original license notices.
    rev = lock['translations']['source_commit']
    for filename in ['LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE']:
        try:
            data = get('https://raw.githubusercontent.com/storytold/craft-i18n/' + rev + '/' + filename)
        except urllib.error.HTTPError as error:
            if error.code == 404:continue
            raise
        target = output / 'notices/craft-i18n' / filename
        target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(data)
    return output


def assemble(snapshot, artifacts, work, sdk):
    project = work / 'lucy';copy_template(project)
    lock = snapshot['engine_lock']
    for i, engine in enumerate(lock['engines']):
        name = engine['id'];folder = artifacts / name
        actual = json.loads((folder / 'engine.json').read_text())
        if actual['id'] != name or actual['source_commit'] != snapshot['heads'][name]:
            raise BuildError('El artefacto no corresponde a la fuente solicitada: ' + name)
        lock['engines'][i] = actual
        shutil.copytree(folder / 'engine', project / 'app/src/main/assets/engines' / name)
        shutil.copyfile(folder / 'adapter.patch', project / 'third_party/patches' / (name + '.patch'))
        shutil.copytree(folder / 'notices', project / 'third_party', dirs_exist_ok=True)
    json_file(project / 'engine-lock.json', lock)
    script = project / 'scripts/build_engines.py'
    run([sys.executable, script, '--verify'])
    info = {'schema': 1, 'request_id': snapshot['request_id'], 'heads': snapshot['heads'],
            'version_name': snapshot['version_name'], 'version_code': snapshot['version_code'],
            'fonts': lock['fonts'], 'translations': lock['translations'], 'engines': lock['engines'],
            'adapter_version': snapshot['adapter_version'], 'source_branch': 'main',
            'built_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'package_name': 'io.github.pedroguille.folio', 'signed': False}
    provenance = {**info, 'ui_languages': ['es'], 'patch_sha256': {
        e['id']: hash_file(project / 'third_party/patches' / (e['id'] + '.patch')) for e in lock['engines']}}
    json_file(project / 'third_party/SOURCES.json', provenance)
    notices = ['Lucy: compilación personal desde GitHub main.\nLa firma se aplica en el dispositivo del usuario.\n']
    for p in sorted((project / 'third_party').rglob('*')):
        if p.is_file() and not any(x in p.relative_to(project / 'third_party').parts for x in ['patches', 'spanish']):
            notices += ['\n' + '=' * 70 + '\n' + p.relative_to(project).as_posix() + '\n', p.read_bytes().decode('utf-8')]
    (project / 'app/src/main/assets/THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices))
    manifest = project / 'app/src/main/AndroidManifest.xml'
    ns = '{http://schemas.android.com/apk/res/android}'
    ET.register_namespace('android', ns[1:-1]);tree = ET.parse(manifest)
    tree.getroot().set(ns + 'versionName', snapshot['version_name'])
    tree.getroot().set(ns + 'versionCode', str(snapshot['version_code']))
    tree.write(manifest, encoding='utf-8', xml_declaration=True)
    apk = package_unsigned(project, sdk)
    output = work / 'result';output.mkdir()
    shutil.copyfile(apk, output / 'Lucy-unsigned.apk')
    info['apk_sha256'] = hash_file(apk)
    json_file(output / 'build-info.json', info)
    # Source archive is reproducible input, not a private key or compiled binary.
    with ZipFile(output / 'Lucy-source.zip', 'w', ZIP_DEFLATED, compresslevel=9) as z:
        for current, dirs, files in os.walk(project):
            dirs[:] = sorted(d for d in dirs if d not in {'.cache', 'build', '.git', '__pycache__', 'node_modules'} and not (
                Path(current).relative_to(project).as_posix() == 'app/src/main/assets' and d == 'engines'))
            for name in sorted(files):
                p = Path(current) / name
                if p.suffix in {'.jks', '.keystore', '.pyc', '.apk'}:continue
                z.write(p, 'Lucy-source/' + p.relative_to(project).as_posix())
    return output


def package_unsigned(project, sdk):
    tools = sdk / 'build-tools/36.0.0';jar = sdk / 'platforms/android-36/android.jar'
    if not jar.is_file() or not (tools / 'aapt2').is_file():
        # GitHub runners can install these automatically through sdkmanager.
        raise BuildError('Faltan Android SDK 36 y build-tools 36.0.0')
    stage = project / 'build'
    for directory in ['classes', 'generated', 'dex']:(stage / directory).mkdir(parents=True)
    run([sys.executable, project / 'scripts/create_templates.py'], project)
    run([tools / 'aapt2', 'compile', '--dir', project / 'app/src/main/res', '-o', stage / 'resources.zip'])
    run([tools / 'aapt2', 'link', '-o', stage / 'linked.apk', '--manifest', project / 'app/src/main/AndroidManifest.xml',
         '-I', jar, '--java', stage / 'generated', '-A', project / 'app/src/main/assets',
         '--min-sdk-version', '26', '--target-sdk-version', '35', stage / 'resources.zip'])
    java = sorted((project / 'app/src/main/java').rglob('*.java')) + sorted((stage / 'generated').rglob('*.java'))
    run(['java', '--module', 'jdk.compiler/com.sun.tools.javac.Main', '--release', '8', '-encoding', 'UTF-8',
         '-classpath', jar, '-d', stage / 'classes', *java])
    run([tools / 'd8', '--release', '--min-api', '26', '--lib', jar, '--output', stage / 'dex', *sorted((stage / 'classes').rglob('*.class'))])
    with ZipFile(stage / 'linked.apk') as linked, ZipFile(stage / 'base.apk', 'w', ZIP_DEFLATED, compresslevel=9) as apk:
        if 'AndroidManifest.xml' not in linked.namelist():raise BuildError('Falta el manifiesto enlazado')
        for item in linked.infolist():apk.writestr(item, linked.read(item.filename), compress_type=item.compress_type, compresslevel=9)
        for dex in sorted((stage / 'dex').glob('*.dex')):apk.write(dex, dex.name)
    run([tools / 'zipalign', '-f', '4', stage / 'base.apk', stage / 'Lucy-unsigned.apk'])
    with ZipFile(stage / 'Lucy-unsigned.apk') as z:
        if z.testzip() or not {'AndroidManifest.xml', 'classes.dex', 'resources.arsc'} <= set(z.namelist()):
            raise BuildError('La APK no está completa')
    return stage / 'Lucy-unsigned.apk'


def main():
    p = argparse.ArgumentParser(description=__doc__);sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('resolve');r.add_argument('--output', type=Path, required=True)
    c = sub.add_parser('compile');c.add_argument('--snapshot', type=Path, required=True);c.add_argument('--engine', choices=REPOS, required=True);c.add_argument('--work', type=Path, required=True)
    a = sub.add_parser('assemble');a.add_argument('--snapshot', type=Path, required=True);a.add_argument('--artifacts', type=Path, required=True);a.add_argument('--work', type=Path, required=True);a.add_argument('--sdk', type=Path, required=True)
    args = p.parse_args()
    if args.command == 'resolve':
        heads = json.loads(os.environ['LUCY_HEADS_JSON'])
        json_file(args.output, resolve_snapshot(heads, os.environ['LUCY_REQUEST_ID'], os.environ.get('GITHUB_RUN_NUMBER', '1')))
    else:
        snapshot = json.loads(args.snapshot.read_text());validate_heads(snapshot['heads'])
        if args.command == 'compile':compile_engine(snapshot, args.engine, args.work.resolve())
        else:assemble(snapshot, args.artifacts.resolve(), args.work.resolve(), args.sdk.resolve())


if __name__ == '__main__':
    try:main()
    except (BuildError, subprocess.CalledProcessError, OSError, ValueError) as error:
        print('ERROR DE COMPILACIÓN:', error, file=sys.stderr);sys.exit(1)
