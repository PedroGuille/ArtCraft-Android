"""Restore upstream language code without restoring removed product panels."""
from pathlib import Path
import re,subprocess

def git(source,*args):
 return subprocess.check_output(['git',*args],cwd=source)

def original(source,path):
 return git(source,'show','HEAD:'+path)

def put(source,path):
 p=source/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(original(source,path))

def deck_patch(patch):
 selected=[]
 for section in re.split(r'(?=^diff --git )',patch.read_text(),flags=re.M):
  if not section.startswith('diff'):continue
  path=section.splitlines()[0].split(' b/')[1]
  parts=re.split(r'(?=^@@)',section,flags=re.M);header=parts[0]
  keep=[]
  for h in parts[1:]:
   yes=path in {'Cargo.toml','apps/deckcraft-web/index.html','crates/ui-egui/src/app.rs','crates/ui-egui/src/folio.rs','crates/ui-egui/src/theme.rs','docs/folio-android.md'}
   if path.endswith('/lib.rs'):yes='mod folio;' in h
   if path.endswith('/ribbon.rs'):yes='let h = ' in h
   if path.endswith('/backstage.rs'):yes='Page::About' in h or 'use info::' in h
   if path.endswith('/backstage/info.rs'):yes='fn about(' in h
   if yes:keep.append(h)
  if keep:selected.append(re.sub(r'^index .*\n','',header,flags=re.M)+''.join(keep))
 patch.write_text(''.join(selected))

def restore(source,name):
 if name=='deckcraft':
  # The original DeckCraft UI is English. Its Spanish fork remains a separate
  # selectable profile; never advertise languages the upstream app lacks.
  p=source/'crates/ui-egui/src/backstage.rs';s=p.read_text()
  labels={'Inicio':'Home','Nuevo':'New','Abrir':'Open','Información':'Info','Guardar como':'Save As','Imprimir':'Print','Exportar':'Export'}
  for a,b in labels.items():s=s.replace('"'+a+'"','"'+b+'"')
  s=re.sub(r'        // Keep existing control-channel callers.*?\n        \}\n','',s,flags=re.S)
  p.write_text(s)
  lib=source/'crates/ui-egui/src/lib.rs';text=lib.read_text()
  text='\n'.join(line for line in text.split('\n') if '("app.about",' not in line and '("app.links",' not in line);lib.write_text(text)
  menus=source/'crates/ui-egui/src/menus.rs';text=menus.read_text().replace('("About DeckCraft", "app.about"), ', '');menus.write_text(text)
  t=source/'crates/ui-egui/src/backstage/tests.rs'
  if t.exists():
   tests=t.read_text().replace('Page::parse("account"), Some(Page::About)','Page::parse("account"), None').replace('Page::parse("about"), Some(Page::About)','Page::parse("about"), None').replace('vec![Nav::Page(Page::About), Nav::Options]','vec![Nav::Options]').replace('[(Page, &str); 8]','[(Page, &str); 7]').replace('        (Page::About, "Credits"),\n','')
   tests=re.sub(r'/// About replaces the account entry.*?\nfn about_has_product_links_and_credits_without_account_controls\(\) \{.*?\n\}\n','',tests,flags=re.S);t.write_text(tests)
  return
 for path in git(source,'ls-tree','-r','--name-only','HEAD','--','crates/ui-egui/src/i18n','crates/ui-egui/src/i18n.rs').decode().splitlines():put(source,path)
 if name=='wordcraft':
  p=source/'crates/ui-egui/build.rs';s=p.read_text().replace('        if code != "es" {\n            continue;\n        }\n','');p.write_text(s)
  p=source/'crates/ui-egui/src/options.rs';s=p.read_text();upstream=original(source,'crates/ui-egui/src/options.rs').decode()
  for fn in ['language','language_picker']:
   pattern=r'^fn '+fn+r'\([^\n]*\{.*?^}'
   old=re.search(pattern,upstream,re.M|re.S)
   if old is None:raise ValueError('No se encontró el selector de idiomas de WordCraft: '+fn)
   current=re.search(pattern,s,re.M|re.S)
   if current:s=s[:current.start()]+old[0]+s[current.end():]
   else:s+='\n'+old[0]+'\n'
  p.write_text(s)
 if name=='gridcraft':
  font='crates/ui-egui/src/theme/font_setup.rs';p=source/font;current=p.read_text()
  inserts=[line for line in current.splitlines() if 'crate::folio::install_ui_fonts(' in line]
  restored=original(source,font).decode()
  if inserts:
   anchor='    fonts\n}'
   if anchor not in restored:raise ValueError('Cambió la preparación de fuentes de GridCraft')
   restored=restored.replace(anchor,'\n'.join(inserts)+'\n'+anchor,1)
  p.write_text(restored)
  for path in ['apps/gridcraft-web/src/prefs.rs','crates/ui-egui/src/app/commands.rs','crates/ui-egui/src/ribbon/view.rs']:
   put(source,path)
 if name=='pdfcraft':put(source,'crates/ui-egui/src/dialogs/preferences.rs')
 if name in {'wordcraft','pdfcraft'}:
  for p in (source/'crates/ui-egui/src').rglob('*.rs'):
   s=p.read_text();new=s.replace('Lang::ES','Lang::EN')
   if s!=new:p.write_text(new)
