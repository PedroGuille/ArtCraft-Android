#!/usr/bin/env python3
"""Package the Python application as an actual installable Flatpak bundle.

No compiled engines, APK signing keys or user caches enter this bundle.
The equivalent flatpak-builder manifest is shipped in flatpak/.
"""
from pathlib import Path
import argparse,base64,json,os,shutil,subprocess,tempfile

ROOT=Path(__file__).resolve().parent
APP='io.github.pedroguille.LucyBuilder'
VERSION='2.3.0'

def run(*args):subprocess.run(list(map(str,args)),check=True)

def icon():
    picture=ROOT/'engine/pipeline/lucy/app/src/main/res/drawable-nodpi/lucy_icon.jpg'
    svg='<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="256" height="256" viewBox="0 0 1024 1024"><image width="1024" height="1024" xlink:href="data:image/jpeg;base64,'+base64.b64encode(picture.read_bytes()).decode()+'"/></svg>\n'
    (ROOT/'flatpak'/str(APP+'.svg')).write_text(svg)

def app_tree(path):
    files=path/'files';lib=files/'lib/lucy-builder';lib.mkdir(parents=True)
    for directory in ['app','engine','native-cad']:
        shutil.copytree(ROOT/directory,lib/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git','.cache','cache','work','target','dist','*.p12','*.pfx','*.jks','*.keystore','*.apk'))
    for name in ['README.md','LICENSE','VALIDACION-'+VERSION+'.md']:shutil.copy2(ROOT/name,lib/name)
    for source,dest in [('lucy-builder','bin/lucy-builder'),(APP+'.desktop','share/applications/'+APP+'.desktop'),(APP+'.metainfo.xml','share/metainfo/'+APP+'.metainfo.xml'),(APP+'.svg','share/icons/hicolor/scalable/apps/'+APP+'.svg')]:
        target=files/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'flatpak'/source,target);target.chmod(0o755 if source=='lucy-builder' else 0o644)
    manifest=json.loads((ROOT/'flatpak'/str(APP+'.json')).read_text())
    context='[Context]\nshared=network;ipc;\nsockets=wayland;fallback-x11;\ndevices=dri;\nfeatures=devel;\nfilesystems=xdg-download/Lucy-Builds:create;\n'
    metadata='[Application]\nname='+APP+'\nruntime=org.gnome.Sdk/x86_64/51\nsdk=org.gnome.Sdk/x86_64/51\ncommand=lucy-builder\n\n'+context
    (path/'metadata').write_text(metadata)
    (files/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'dist');args=parser.parse_args()
    if not shutil.which('flatpak'):parser.error('Instalá flatpak para crear el paquete.')
    args.output.mkdir(parents=True,exist_ok=True);icon()
    with tempfile.TemporaryDirectory(prefix='flatpak-',dir=args.output) as temporary:
        work=Path(temporary);tree=work/'build';app_tree(tree)
        run('flatpak','build-finish',tree)
        run('flatpak','build-export','--disable-sandbox','--arch=x86_64',work/'repo',tree,'stable')
        bundle=args.output/('Lucy-Builder-'+VERSION+'-x86_64.flatpak')
        run('flatpak','build-bundle','--arch=x86_64','--runtime-repo=https://flathub.org/repo/flathub.flatpakrepo',work/'repo',bundle,APP,'stable')
    print(bundle)

if __name__=='__main__':main()
