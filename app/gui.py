#!/usr/bin/env python3
"""Native GTK/Libadwaita interface for local Android source builds."""
from pathlib import Path
import json,os,signal,subprocess,sys,threading,time,uuid,zipfile,io
import gi
gi.require_version('Gtk','4.0');gi.require_version('Adw','1')
from gi.repository import Gtk,Adw,Gio,GLib,Gdk
from .catalog import APPS,BY_ID,OFFICE
from .revisions import MODES,LABELS,selected_index
from .core import ROOT,legacy

APP_ID='io.github.pedroguille.LucyBuilder'

def label(text,css=None,wrap=False):
 item=Gtk.Label(label=text,xalign=0,wrap=wrap)
 if css:item.add_css_class(css)
 return item

class BuilderWindow(Adw.ApplicationWindow):
 def __init__(self,app,state=None):
  super().__init__(application=app,title='Lucy Builder',default_width=1120,default_height=820)
  self.state=Path(state) if state else Path(GLib.get_user_data_dir())/'lucy-builder-2'
  self.state.mkdir(parents=True,exist_ok=True);self.state.chmod(0o700)
  self.settings=self.load('settings.json',{});self.history=self.load('history.json',[])
  for job in self.history:
   if job.get('status') in {'building','cancelling'}:job['status']='interrupted'
  self.process=None;self.current_job=None;self.cards={};self.office_checks={};self.results={};self.close_after_cancel=False
  self.toast=Adw.ToastOverlay();outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);self.toast.set_child(outer);self.set_content(self.toast)
  header=Adw.HeaderBar();header.set_title_widget(Adw.WindowTitle(title='Lucy Builder',subtitle='Código fuente → APK Android'));outer.append(header)
  split=Gtk.Box();outer.append(split);split.set_vexpand(True)
  sidebar=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,width_request=206)
  sidebar.add_css_class('sidebar');sidebar.set_margin_top(16);sidebar.set_margin_bottom(16);sidebar.set_margin_start(12);sidebar.set_margin_end(12)
  sidebar.append(label('CONSTRUCTOR ANDROID','caption-heading'))
  self.navigation=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE);self.navigation.add_css_class('navigation-sidebar')
  pages=[('applications','Aplicaciones','view-grid-symbolic'),('lucy','Componer Lucy','view-dual-symbolic'),('history','Compilaciones','folder-download-symbolic'),('settings','Configuración','emblem-system-symbolic')]
  for key,title,icon in pages:
   row=Gtk.ListBoxRow();row.page_name=key;box=Gtk.Box(spacing=12);box.set_margin_top(10);box.set_margin_bottom(10);box.set_margin_start(10);box.set_margin_end(10);box.append(Gtk.Image.new_from_icon_name(icon));box.append(label(title));row.set_child(box);self.navigation.append(row)
  sidebar.append(self.navigation);spacer=Gtk.Box(vexpand=True);sidebar.append(spacer)
  sidebar.append(label('Local en tu PC','heading'));sidebar.append(label('Fuentes, herramientas y firmas\nen una caché reutilizable.','dim-label'))
  sidebar.append(label('Versión 2.3.1','caption'));split.append(sidebar);split.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
  self.stack=Gtk.Stack(hexpand=True,vexpand=True,transition_type=Gtk.StackTransitionType.CROSSFADE)
  split.append(self.stack)
  self.stack.add_named(self.applications_page(),'applications');self.stack.add_named(self.lucy_page(),'lucy');self.stack.add_named(self.history_page(),'history');self.stack.add_named(self.settings_page(),'settings')
  self.navigation.connect('row-selected',lambda box,row:self.stack.set_visible_child_name(row.page_name) if row else None)
  self.navigation.select_row(self.navigation.get_row_at_index(0))
  self.connect('close-request',self.close_requested)
  self.refresh_history();self.update_selection()

 def load(self,name,default):
  try:return json.loads((self.state/name).read_text())
  except (OSError,ValueError):return default
 def save(self,name,value):legacy.save_json(self.state/name,value)
 def notify(self,text):self.toast.add_toast(Adw.Toast(title=text,timeout=6))
 def page(self,title,subtitle):
  scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20)
  for setter in ['set_margin_top','set_margin_bottom','set_margin_start','set_margin_end']:getattr(box,setter)(28)
  box.append(label(title,'title-1'));box.append(label(subtitle,'dim-label',True));scroll.set_child(box);return scroll,box
 def action(self,text,callback,suggested=False):
  button=Gtk.Button(label=text);button.connect('clicked',callback)
  if suggested:button.add_css_class('suggested-action')
  return button
 def icon(self,name,size=48):
  path=ROOT/'app/icons'/str(name+'.png')
  image=Gtk.Image.new_from_file(str(path)) if path.exists() else Gtk.Image.new_from_icon_name('application-x-executable-symbolic')
  image.set_pixel_size(size);return image

 def applications_page(self):
  page,box=self.page('Aplicaciones individuales','Elegí las aplicaciones que querés generar. Cada una tendrá su propia APK y su propio icono.')
  actions=Gtk.Box(spacing=10);actions.append(self.action('Seleccionar compatibles',lambda _:self.select_all()));actions.append(self.action('Quitar selección',lambda _:self.select_all(False)));box.append(actions)
  self.app_count=label('','heading');box.append(self.app_count)
  footer=Gtk.Box(spacing=10);self.download_button=self.action('Descargar fuentes',lambda _:self.start('individual',True));self.individual_button=self.action('Compilar APK individuales',lambda _:self.start('individual'),True);footer.append(self.download_button);footer.append(self.individual_button);box.append(footer)
  grid=Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,min_children_per_line=1,max_children_per_line=3,column_spacing=12,row_spacing=12,homogeneous=True)
  for app in APPS:
   frame=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);frame.add_css_class('card');card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10,width_request=238);frame.append(card)
   for setter in ['set_margin_top','set_margin_bottom','set_margin_start','set_margin_end']:getattr(card,setter)(16)
   top=Gtk.Box(spacing=12);top.append(self.icon(app.id));text=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3);text.append(label(app.name,'heading'));tag='APK Android' if app.recipe in {'office','native'} else ('Versión web adaptada' if app.recipe=='web' else 'Solo código fuente');text.append(label(tag,'caption'));top.append(text)
   check=Gtk.CheckButton();check.set_hexpand(True);check.set_halign(Gtk.Align.END);check.set_tooltip_text('Seleccionar '+app.name);check.connect('toggled',lambda _:self.update_selection());top.append(check);card.append(top);card.append(label(app.description,'dim-label',True));grid.append(frame);self.cards[app.id]=check
  box.append(grid)
  box.append(label('Las adaptaciones web utilizan el código real de cada aplicación dentro de Android. Su compatibilidad depende de Android System WebView. Las tarjetas «Solo código fuente» no ofrecen una APK compatible.','caption',True))
  return page

 def lucy_page(self):
  page,box=self.page('Componer Lucy','Una aplicación Android con los editores que elijas. Incluí de uno a cuatro; los que no marques quedarán fuera de la APK y de sus menús.')
  preview=Gtk.Box(spacing=18);path=ROOT/'engine/pipeline/lucy/app/src/main/res/drawable-nodpi/lucy_icon.jpg';pic=Gtk.Picture.new_for_filename(str(path));pic.set_size_request(96,96);pic.set_can_shrink(True);preview.append(pic)
  intro=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5);intro.append(label('Lucy, a tu medida','title-2'));intro.append(label('Español · pestañas · vista dividida · modo oscuro','dim-label',True));preview.append(intro);box.append(preview)
  group=Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE);group.add_css_class('boxed-list')
  descriptions={'wordcraft':'Documentos Word y texto','pdfcraft':'Archivos PDF','gridcraft':'Hojas de cálculo','deckcraft':'Presentaciones'}
  for name in OFFICE:
   row=Adw.ActionRow(title=BY_ID[name].name,subtitle=descriptions[name]);row.add_prefix(self.icon(name,38));check=Gtk.CheckButton(active=True,valign=Gtk.Align.CENTER);check.connect('toggled',lambda _:self.update_selection());row.add_suffix(check);row.set_activatable_widget(check);self.office_checks[name]=check;group.append(row)
  box.append(group);self.suite_count=label('','heading');box.append(self.suite_count)
  actions=Gtk.Box(spacing=10);self.lucy_download=self.action('Descargar fuentes elegidas',lambda _:self.start('lucy',True));self.lucy_button=self.action('Compilar Lucy',lambda _:self.start('lucy'),True);actions.append(self.lucy_download);actions.append(self.lucy_button);box.append(actions)
  box.append(label('La firma de Lucy se conserva al cambiar su selección. Para actualizar una instalación anterior, importá primero su firma en Configuración.','caption',True));return page

 def settings_page(self):
  page,box=self.page('Configuración','Las herramientas se preparan automáticamente. Las opciones se guardan en este equipo.')
  out=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);out.append(label('Carpeta de resultados','heading'))
  line=Gtk.Box(spacing=8);downloads=GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or str(Path.home()/'Downloads')
  self.output_entry=Gtk.Entry(text=self.settings.get('output',str(Path(downloads)/'Lucy-Builds')),hexpand=True);line.append(self.output_entry);line.append(self.action('Elegir…',lambda _:self.choose_folder()));out.append(line);box.append(out)
  options=Gtk.Box(spacing=20);left=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);left.append(label('Fuentes a compilar','heading'));self.revisions=Gtk.DropDown.new_from_strings(list(LABELS));self.revisions.set_selected(selected_index(self.settings));left.append(self.revisions);options.append(left)
  right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);right.append(label('Trabajos simultáneos','heading'));self.jobs=Gtk.SpinButton.new_with_range(1,32,1);self.jobs.set_value(int(self.settings.get('jobs',legacy.default_jobs())));right.append(self.jobs);options.append(right);box.append(options)
  box.append(label('Las revisadas fijan las fuentes actuales de los cuatro editores y CADCraft. El resto conserva sus referencias base. Las versiones anteriores siguen disponibles. Una publicación nueva o main puede requerir actualizar su adaptador. No se cambia de versión automáticamente si falla.','caption',True))
  versions=json.loads((ROOT/'app/verified.json').read_text());box.append(label('Base fija: '+', '.join(BY_ID[n].name+' '+versions.get('versions',{}).get(n,h[:8]) for n,h in versions['heads'].items()),'caption',True))
  box.append(label('Idiomas de las aplicaciones generadas','heading'));self.languages=Gtk.DropDown.new_from_strings(['Todos los idiomas de origen','Perfil anterior · solo español']);self.languages.set_selected(int(self.settings.get('language_mode',0)));box.append(self.languages)
  box.append(label('Se restauran los idiomas y selectores de cada proyecto. DeckCraft ofrece inglés en su interfaz original; el perfil anterior conserva su adaptación española. Los idiomas disponibles dependen de la aplicación.','caption',True))
  box.append(Gtk.Separator());box.append(label('Firma de las APK','title-3'))
  self.key_status=label('Cada aplicación conserva su propia firma. La importación se aplica a las aplicaciones de la próxima compilación.','dim-label',True);box.append(self.key_status)
  row=Gtk.Box(spacing=8);self.key_entry=Gtk.Entry(placeholder_text='Firma anterior: JKS, PKCS12 o ZIP',hexpand=True);row.append(self.key_entry);row.append(self.action('Importar archivo…',lambda _:self.choose_key()));box.append(row)
  self.key_password=Gtk.PasswordEntry(show_peek_icon=True,placeholder_text='Contraseña de la firma anterior (vacío: android)');box.append(self.key_password)
  self.signing_scope=Gtk.DropDown.new_from_strings(['Lucy']+[app.name for app in APPS if app.recipe!='source']);box.append(self.signing_scope)
  box.append(self.action('Respaldar la firma elegida…',lambda _:self.backup_key()))
  box.append(Gtk.Separator());box.append(label('Herramientas de Android','title-3'))
  self.accept_sdk=Gtk.CheckButton(label='He leído y acepto la licencia del SDK de Android',active=bool(self.settings.get('accept_sdk_license',False)));box.append(self.accept_sdk)
  link=Gtk.LinkButton(uri='https://developer.android.com/studio/terms',label='Leer licencia oficial de Google');link.set_halign(Gtk.Align.START);box.append(link)
  box.append(label('La primera compilación descarga SDK, JDK y Rust y puede tardar. Después se reutilizan las herramientas y los motores cuyos archivos coincidan.','caption',True));box.append(label('Datos y caché: '+str(self.state),'caption',True));return page

 def history_page(self):
  page,box=self.page('Compilaciones','Seguí el progreso y abrí las APK, sus informes o las fuentes descargadas.')
  self.progress_title=label('Listo para compilar','title-3');box.append(self.progress_title);self.progress=Gtk.ProgressBar(show_text=True);box.append(self.progress)
  self.current_detail=label('Elegí una aplicación o componé Lucy para empezar.','dim-label',True);box.append(self.current_detail)
  self.cancel_button=self.action('Cancelar compilación',lambda _:self.cancel());self.cancel_button.add_css_class('destructive-action');self.cancel_button.set_sensitive(False);self.cancel_button.set_halign(Gtk.Align.START);box.append(self.cancel_button)
  self.history_list=Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE);self.history_list.add_css_class('boxed-list');box.append(self.history_list)
  expander=Gtk.Expander(label='Registro detallado');view=Gtk.TextView(editable=False,cursor_visible=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR);self.log_buffer=view.get_buffer();scroll=Gtk.ScrolledWindow(min_content_height=240,max_content_height=360);scroll.set_child(view);expander.set_child(scroll);box.append(expander);return page

 def update_selection(self):
  if not hasattr(self,'individual_button'):return
  selected=[name for name,check in self.cards.items() if check.get_active()];busy=self.process is not None
  self.app_count.set_text(str(len(selected))+' aplicaciones seleccionadas')
  self.download_button.set_sensitive(bool(selected) and not busy);self.individual_button.set_sensitive(bool(selected) and not busy and all(BY_ID[n].recipe!='source' for n in selected))
  if hasattr(self,'lucy_button'):
   count=sum(check.get_active() for check in self.office_checks.values());self.suite_count.set_text(str(count)+' de 4 editores · una APK de Lucy')
   self.lucy_button.set_sensitive(count>0 and not busy);self.lucy_download.set_sensitive(count>0 and not busy)
 def select_all(self,active=True):
  for name,check in self.cards.items():check.set_active(active and BY_ID[name].recipe!='source')
 def switch(self,name):
  for index in range(4):
   row=self.navigation.get_row_at_index(index)
   if row.page_name==name:self.navigation.select_row(row);break

 def choose_folder(self):
  dialog=Gtk.FileDialog(title='Carpeta de resultados')
  def done(obj,result):
   try:
    file=obj.select_folder_finish(result)
    if file.get_path():self.output_entry.set_text(file.get_path())
   except GLib.Error:pass
  dialog.select_folder(self,None,done)
 def choose_key(self):
  dialog=Gtk.FileDialog(title='Importar firma anterior')
  def done(obj,result):
   try:
    file=obj.open_finish(result)
    if file.get_path():self.key_entry.set_text(file.get_path())
   except GLib.Error:pass
  dialog.open(self,None,done)
 def open_file(self,path):
  Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(str(path)).get_uri(),None)
 def backup_key(self):
  ids=['lucy']+[app.id for app in APPS if app.recipe!='source'];slug=ids[self.signing_scope.get_selected()]
  folder=self.state/'compiler/identities'/slug/'signing/current'
  if not (folder/'lucy.p12').is_file():self.notify('Primero compilá una APK para crear tu firma.');return
  dialog=Gtk.FileDialog(title='Guardar copia privada de firma',initial_name=slug+'-firma-privada.zip')
  def done(obj,result):
   try:
    target=obj.save_finish(result);data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as archive:
     archive.writestr('lucy.p12',(folder/'lucy.p12').read_bytes());archive.writestr('password.txt',(folder/'password.txt').read_bytes());archive.writestr('LEEME.txt','Copia privada de tu firma Android. Conservá esta carpeta y su contraseña para actualizar tus APK. No publiques esta copia.\n')
    target.replace_contents(data.getvalue(),None,False,Gio.FileCreateFlags.PRIVATE,None);self.notify('Copia privada de la firma guardada.')
   except GLib.Error as error:self.notify(str(error))
  dialog.save(self,None,done)

 def persist_settings(self):
  self.settings={'output':self.output_entry.get_text(),'jobs':int(self.jobs.get_value()),'revision_mode':self.revisions.get_selected(),'revision_schema':3,'language_mode':self.languages.get_selected(),'accept_sdk_license':self.accept_sdk.get_active()};self.save('settings.json',self.settings)
 def start(self,mode,download=False):
  if self.process:return
  ids=[name for name,check in (self.office_checks if mode=='lucy' else self.cards).items() if check.get_active()]
  if not ids:self.notify('Seleccioná al menos una aplicación.');return
  if not download and not self.accept_sdk.get_active() and not (self.state/'compiler/tools/android-sdk/lucy-license-receipt.json').exists():self.notify('Leé y aceptá la licencia del SDK en Configuración.');self.switch('settings');return
  output=self.output_entry.get_text().strip()
  if not output:self.notify('Elegí una carpeta de resultados.');self.switch('settings');return
  self.persist_settings();job_id=uuid.uuid4().hex
  job={'id':job_id,'mode':mode,'apps':ids,'download_only':download,'output':output,'jobs':int(self.jobs.get_value()),'revision_mode':MODES[self.revisions.get_selected()],'language_mode':'all' if self.languages.get_selected()==0 else 'es','accept_sdk_license':self.accept_sdk.get_active(),'import_key':self.key_entry.get_text().strip()}
  requests=self.state/'requests';requests.mkdir(exist_ok=True);path=requests/(job_id+'.json');legacy.save_json(path,job)
  env=dict(os.environ)
  if job['import_key']:env['LUCY_IMPORT_PASSWORD']=self.key_password.get_text() or 'android'
  self.key_password.set_text('');self.key_entry.set_text('')
  self.current_job={'id':job_id,'name':'Lucy' if mode=='lucy' else ', '.join(BY_ID[n].name for n in ids),'status':'building','time':time.strftime('%d/%m/%Y %H:%M'),'results':[],'sources':[]}
  self.history.insert(0,self.current_job);self.history=self.history[:100];self.save('history.json',self.history);self.log_buffer.set_text('');self.progress.set_fraction(0);self.progress_title.set_text('Iniciando…');self.cancel_button.set_sensitive(True)
  try:self.process=subprocess.Popen([sys.executable,'-u','-m','app.worker','--job',str(path),'--state',str(self.state/'compiler')],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
  except OSError as error:self.current_job['status']='failed';self.notify(str(error));self.process=None;self.update_selection();return
  process=self.process
  def consume():
   for line in process.stdout:GLib.idle_add(self.on_line,line)
   code=process.wait();GLib.idle_add(self.on_exit,process,code)
  threading.Thread(target=consume,daemon=True).start();self.update_selection();self.refresh_history();self.switch('history')

 def on_line(self,line):
  self.log_buffer.insert(self.log_buffer.get_end_iter(),line)
  if self.log_buffer.get_line_count()>1400:
   start=self.log_buffer.get_start_iter();end=self.log_buffer.get_iter_at_line(400);end=end[1] if isinstance(end,tuple) else end;self.log_buffer.delete(start,end)
  if not line.startswith('@LUCY '):return False
  try:data=json.loads(line[6:])
  except ValueError:return False
  event=data.get('event')
  if event=='stage':self.progress.set_fraction(float(data.get('fraction',0)));self.progress_title.set_text(data.get('title',''))
  elif event=='application':self.current_detail.set_text(f"{data['index']} de {data['total']} · {data['name']}")
  elif event=='started':self.current_job['log']=data.get('log')
  elif event=='revisions':self.current_detail.set_text(' · '.join(name+': '+sha[:10] for name,sha in data['heads'].items()))
  elif event=='result':self.current_job['results'].append(data['result']);self.refresh_history()
  elif event=='sources':self.current_job['sources'].extend(data['paths']);self.refresh_history()
  elif event=='failed':self.current_job['error']=data.get('message');self.current_detail.set_text(data.get('message','Error'))
  elif event=='cancelled':self.current_job['status']='cancelled'
  return False
 def on_exit(self,process,code):
  if process is not self.process:return False
  self.process=None;status=self.current_job.get('status');self.current_job['status']='success' if code==0 else ('cancelled' if status in {'cancelling','cancelled'} or code in {130,-2,-15} else 'failed')
  if code==0:self.progress.set_fraction(1);self.progress_title.set_text('Terminado');self.current_detail.set_text('Los resultados están listos para abrir.')
  elif self.current_job['status']=='cancelled':self.progress_title.set_text('Cancelado');self.current_detail.set_text('La firma, las APK anteriores y la caché válida se conservan.')
  else:self.progress_title.set_text('No se completó');self.current_detail.set_text(self.current_job.get('error','Consultá el registro para ver el motivo.'))
  self.cancel_button.set_sensitive(False);self.save('history.json',self.history);self.update_selection();self.refresh_history()
  if self.close_after_cancel:self.destroy()
  return False
 def cancel(self):
  if not self.process:return
  process=self.process;self.current_job['status']='cancelling';self.progress_title.set_text('Cancelando…')
  try:os.killpg(process.pid,signal.SIGINT)
  except ProcessLookupError:pass
  def force(sig):
   if process.poll() is None:
    try:os.killpg(process.pid,sig)
    except ProcessLookupError:pass
   return False
  GLib.timeout_add_seconds(5,force,signal.SIGTERM);GLib.timeout_add_seconds(10,force,signal.SIGKILL)
 def refresh_history(self):
  child=self.history_list.get_first_child()
  while child:next_item=child.get_next_sibling();self.history_list.remove(child);child=next_item
  if not self.history:self.history_list.append(Adw.ActionRow(title='Todavía no hay compilaciones',subtitle='Las APK generadas aparecerán aquí.'));return
  labels={'building':'En curso','success':'Completado','failed':'Error','cancelled':'Cancelado','cancelling':'Cancelando','interrupted':'Interrumpido'}
  for job in self.history:
   row=Adw.ExpanderRow(title=job['name'],subtitle=job['time']+' · '+labels.get(job['status'],job['status']))
   for result in job.get('results',[]):
    item=Adw.ActionRow(title=Path(result['apk']).name,subtitle=str(result.get('version_name',''))+' · '+str(len(result.get('selection',[])))+' editor(es)');button=self.action('Abrir carpeta',lambda _,p=result['output']:self.open_file(p));button.set_valign(Gtk.Align.CENTER);item.add_suffix(button);row.add_row(item)
   for path in job.get('sources',[]):
    item=Adw.ActionRow(title='Código fuente',subtitle=str(path));button=self.action('Abrir',lambda _,p=path:self.open_file(p));button.set_valign(Gtk.Align.CENTER);item.add_suffix(button);row.add_row(item)
   if job.get('log'):
    item=Adw.ActionRow(title='Registro de compilación');button=self.action('Ver registro',lambda _,p=job['log']:self.open_file(p));button.set_valign(Gtk.Align.CENTER);item.add_suffix(button);row.add_row(item)
   self.history_list.append(row)
 def close_requested(self,_):
  self.persist_settings()
  if not self.process:return False
  dialog=Adw.MessageDialog(transient_for=self,heading='Hay una compilación en curso',body='Podés esperar a que termine o cancelarla antes de cerrar.');dialog.add_response('keep','Seguir compilando');dialog.add_response('cancel','Cancelar y cerrar');dialog.set_default_response('keep');dialog.set_close_response('keep');dialog.set_response_appearance('cancel',Adw.ResponseAppearance.DESTRUCTIVE)
  def response(obj,value):
   if value=='cancel':self.close_after_cancel=True;self.cancel()
  dialog.connect('response',response);dialog.present();return True

class Application(Adw.Application):
 def __init__(self):super().__init__(application_id=APP_ID,flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
 def do_activate(self):
  window=self.get_active_window()
  if window is None:window=BuilderWindow(self)
  window.present()

def main():
 app=Application();return app.run(sys.argv)
if __name__=='__main__':sys.exit(main())
