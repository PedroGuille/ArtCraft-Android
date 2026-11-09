#!/usr/bin/env python3
"""Reproduce and verify Lucy Builder's CADCraft v0.19.0 Android profile."""
from pathlib import Path
import hashlib, importlib.util, json, os, shutil, subprocess, tempfile, zipfile

ROOT=Path(__file__).resolve().parents[1]
KIT=ROOT/'native-cad'
OLD='a3d9348f63c2ad35391cc93980dc7ee7366f2ad6'
NEW='227e3c385b20129cf525775e3d9cbe78b722b3bb'
PROFILE='release-0.19.0'
spec=importlib.util.spec_from_file_location('cad019_tablet',KIT/'tablet.py')
tablet=importlib.util.module_from_spec(spec);spec.loader.exec_module(tablet)

def git(folder,*args):
    return subprocess.check_output(['git',*map(str,args)],cwd=folder)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def seal():
    blocked={'__pycache__','.git','cache','work','dist','private','target'}
    entries=[sha(p)+'  '+p.relative_to(KIT).as_posix() for p in sorted(KIT.rglob('*'))
             if p.is_file() and not p.is_symlink() and p.name!='CONTENTS.sha256'
             and not set(p.relative_to(KIT).parts)&blocked
             and p.suffix not in {'.pyc','.p12','.pfx','.jks','.keystore','.apk'}]
    (KIT/'CONTENTS.sha256').write_text('\n'.join(entries)+'\n')

def verify(archive,work):
    report=tablet.prepare(archive,work/'verified',KIT)
    assert report['upstream_version']=='0.19.0'
    assert report['source_profile']==PROFILE and not report['conflicts']
    manifest=(work/'verified/packaging/android/AndroidManifest.xml').read_text()
    assert 'android:versionName="0.19.0"' in manifest
    assert 'android:versionCode="19000"' in manifest
    future=work/'future.zip'
    with zipfile.ZipFile(archive) as source,zipfile.ZipFile(future,'w',zipfile.ZIP_DEFLATED) as dest:
        for item in source.infolist():
            data=source.read(item)
            if item.filename=='cadcraft/Cargo.toml':
                assert b'version = "0.19.0"' in data
                data=data.replace(b'version = "0.19.0"',b'version = "0.19.1"',1)
            dest.writestr(item,data)
    report=tablet.prepare(future,work/'future',KIT)
    assert 'source_profile' not in report
    assert report['upstream_version']=='0.19.1' and report['status']=='integration_conflicts'
    print('Verified CADCraft 0.19 integration and rejection of changed future inputs.',flush=True)

def validation(info=None):
    lines=[
        '# Lucy Builder 2.3.1','',
        'CADCraft 0.19.0: etiqueta v0.19.0, commit '+NEW+'.','',
        'El perfil Android revisado conserva las versiones anteriores y comprueba 71 entradas de las fuentes.',
        'La entrega conserva los cuatro editores y sus idiomas de Lucy Builder 2.3.0.','',
        'Las pruebas verifican la integración de la versión publicada y que una versión alterada no reciba este perfil.',
    ]
    if info:
        assert info['heads']['cadcraft']==NEW and info['version_name']=='0.19.0'
        lines.extend(['','Compilación release nativa ARM64 completada mediante el backend de Lucy Builder.',
                      'Firma APK y alineación nativa de 16 KiB verificadas.',
                      'SHA-256 APK: '+info['apk_sha256']+'.'])
    else:
        lines.extend(['','La APK y su firma se verifican en la compilación de esta entrega.'])
    lines.extend(['','No se ha probado en un dispositivo físico. Los editores ofimáticos no se recompilan en esta actualización.',''])
    (ROOT/'VALIDACION-2.3.1.md').write_text('\n'.join(lines))

def update_metadata():
    path=ROOT/'app/reviewed.json';data=json.loads(path.read_text())
    data['heads']['cadcraft']=NEW;data['versions']['cadcraft']='0.19.0';save(path,data)
    for name in ['app/worker.py','app/host.py','app/native_cad.py','app/gui.py',
                 'build_flatpak.py','release_source.py','README.md','tools/current_sources.py']:
        p=ROOT/name;text=p.read_text().replace('2.3.0','2.3.1')
        if name=='tools/current_sources.py':
            text=text.replace("'cadcraft':'"+OLD+"'","'cadcraft':'"+NEW+"'")
            text=text.replace("cadcraft='0.17.0'","cadcraft='0.19.0'")
            text=text.replace('CADCraft-Tablet-0.17.0-arm64-v8a.apk','CADCraft-Tablet-0.19.0-arm64-v8a.apk')
        p.write_text(text)
    p=ROOT/'README.md';text=p.read_text().replace('y CADCraft 0.17.0','y CADCraft 0.19.0')
    if '* **Revisadas · 09/11/2026**:' not in text:
        text=text.replace('En Configuración → Fuentes a compilar:\n',
                          'En Configuración → Fuentes a compilar:\n\n* **Revisadas · 09/11/2026**: incluye CADCraft 0.19.0, fijado por su commit publicado y adaptado a Android.\n',1)
    p.write_text(text)
    p=ROOT/'flatpak/io.github.pedroguille.LucyBuilder.metainfo.xml'
    text=p.read_text()
    if 'version="2.3.1"' not in text:
        text=text.replace('<releases>','<releases><release version="2.3.1" date="2026-11-09"><description><p>Support native Android builds of CADCraft 0.19.0, retaining earlier source profiles.</p></description></release>',1)
    p.write_text(text)
    for name in ['flatpak/io.github.pedroguille.LucyBuilder.json','.github/workflows/build-android.yml']:
        p=ROOT/name;p.write_text(p.read_text().replace('2.3.0','2.3.1').replace('CADCraft-Tablet-0.17.0-arm64-v8a.apk','CADCraft-Tablet-0.19.0-arm64-v8a.apk'))
    validation()

def main():
    adapter=json.loads((KIT/'adapter.json').read_text())
    if any(p.get('source_commit')==NEW for p in adapter.get('source_profiles',[])):
        assert json.loads((ROOT/'app/reviewed.json').read_text())['heads']['cadcraft']==NEW
        print('CADCraft 0.19.0 already reviewed.');return
    base=Path(os.environ.get('RUNNER_TEMP',str(ROOT.parent)))
    with tempfile.TemporaryDirectory(prefix='cad019-port-',dir=base) as temporary:
        work=Path(temporary);raw=work/'raw'
        subprocess.run(['git','clone','--quiet','--no-checkout','--depth','1','--branch','v0.19.0','https://github.com/storytold/cadcraft.git',str(raw)],check=True)
        assert git(raw,'rev-parse','HEAD').decode().strip()==NEW
        git(raw,'fetch','--quiet','--depth=1','origin',OLD)
        reports={}
        for label,commit in [('previous',OLD),('current',NEW)]:
            archive=work/(label+'.zip')
            git(raw,'archive','--format=zip','--prefix=cadcraft/','--output='+str(archive),commit)
            reports[label]=tablet.prepare(archive,work/label,KIT)
        assert not reports['previous']['conflicts']
        previous=next(p for p in adapter['source_profiles'] if p.get('source_commit')==OLD)
        ported=work/'ported'
        subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(raw),str(ported)],check=True)
        git(ported,'checkout','--quiet','--detach',NEW)
        names={p['path'] for p in adapter['modified']+adapter['owned']+previous['files']}
        with tempfile.TemporaryDirectory(dir=work) as merge:
            for name in sorted(names):
                old_port=work/'previous'/name
                if not old_port.is_file():continue
                original=subprocess.run(['git','show',OLD+':'+name],cwd=raw,capture_output=True)
                path=ported/name;target=old_port.read_bytes()
                if original.returncode:
                    if path.exists() and path.read_bytes()!=target:raise RuntimeError('Owned path changed: '+name)
                    combined=target
                else:
                    if not path.is_file():raise RuntimeError('Upstream removed '+name)
                    combined,ok=tablet.merge_one(path.read_bytes(),original.stdout,target,Path(merge))
                    if not ok:raise RuntimeError('Review required: '+name)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(combined);path.chmod(old_port.stat().st_mode&0o777)
        conflicting={r['path'] for r in reports['current']['conflicts']}
        records=[]
        for path in sorted(ported.rglob('*')):
            if not path.is_file() or '.git' in path.relative_to(ported).parts:continue
            name=path.relative_to(ported).as_posix();other=work/'current'/name
            if name not in conflicting and (not other.exists() or other.read_bytes()==path.read_bytes()):continue
            rel='compat/'+PROFILE+'/'+name;dest=KIT/rel
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
            records.append({'path':name,'source':rel,'sha256':sha(dest),'mode':path.stat().st_mode&0o777})
        assert conflicting<={r['path'] for r in records}
        match={}
        for name in set(previous['match'])|{r['path'] for r in adapter['modified']}|{'Cargo.toml','Cargo.lock'}:
            match[name]=hashlib.sha256(git(raw,'show',NEW+':'+name)).hexdigest()
        adapter['adapter_version']='1.4.0-lucy'
        adapter['source_profiles'].append({'id':PROFILE,'source_commit':NEW,'match':dict(sorted(match.items())),'files':records})
        save(KIT/'adapter.json',adapter);update_metadata();seal()
        verify(work/'current.zip',work)
        print('CADCraft 0.19 profile:',len(records),'payloads;',len(match),'guarded inputs.',flush=True)

if __name__=='__main__':main()
