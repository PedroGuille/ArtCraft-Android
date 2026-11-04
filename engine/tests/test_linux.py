from pathlib import Path
import unittest,tempfile,sys,os,json,io,hashlib,subprocess,copy,contextlib,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import lucy,bootstrap

class LinuxTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_output_preserves_unrelated_files(self):
  out=self.root/'output';out.mkdir();(out/'Lucy.apk').write_bytes(b'user file')
  with self.assertRaises(lucy.BuildFailure):lucy.output_root(out)
  self.assertEqual((out/'Lucy.apk').read_bytes(),b'user file')
 def test_output_rejects_external_link(self):
  out=self.root/'output';lucy.output_root(out);(out/'Lucy.apk').symlink_to('/etc/passwd')
  with self.assertRaises(lucy.BuildFailure):lucy.output_root(out)
 def test_output_cannot_publish_through_a_builds_symlink(self):
  out=lucy.output_root(self.root/'output');other=self.root/'other';other.mkdir();(out/'builds').symlink_to(other)
  with self.assertRaises(lucy.BuildFailure):lucy.output_root(out)
  self.assertEqual(list(other.iterdir()),[])
 def test_cache_is_bound_to_inputs_and_bytes(self):
  cache=self.root/'cache';cache.mkdir();(cache/'editor.wasm').write_bytes(b'compiled')
  lucy.save_json(cache/'cache.json',{'cache_key':'correct','commit':'a'*40,'files':{'editor.wasm':bootstrap.digest(cache/'editor.wasm')}})
  self.assertTrue(lucy.cache_valid(cache,'correct','a'*40));self.assertFalse(lucy.cache_valid(cache,'other','a'*40))
  (cache/'editor.wasm').write_bytes(b'modified');self.assertFalse(lucy.cache_valid(cache,'correct','a'*40))
 def test_cache_cannot_escape(self):
  cache=self.root/'cache';cache.mkdir();lucy.save_json(cache/'cache.json',{'cache_key':'k','commit':'a','files':{'../outside':'x'}})
  self.assertFalse(lucy.cache_valid(cache,'k','a'))
 def test_download_verifies_before_replacing(self):
  destination=self.root/'archive';destination.write_bytes(b'previous good')
  class Response(io.BytesIO):
   def __enter__(self):return self
   def __exit__(self,*args):self.close()
  with patch.object(bootstrap.urllib.request,'urlopen',return_value=Response(b'bad')):
   with self.assertRaises(bootstrap.SetupError):bootstrap.download('https://example.invalid/a',destination,'0'*64)
  self.assertEqual(destination.read_bytes(),b'previous good')
 def test_verified_download_is_reused(self):
  destination=self.root/'archive';destination.write_bytes(b'valid')
  with patch.object(bootstrap.urllib.request,'urlopen',side_effect=AssertionError('Network should not be called')):
   bootstrap.download('https://example.invalid/a',destination,bootstrap.digest(destination))
 def test_download_rejects_plain_http(self):
  with self.assertRaises(bootstrap.SetupError):bootstrap.download('http://example.invalid/a',self.root/'a','0'*64)
 def test_sdk_zip_rejects_traversal_and_symlinks(self):
  for filename,mode in [('../escape',0o100644),('link',0o120777)]:
   archive=self.root/'sdk.zip'
   with zipfile.ZipFile(archive,'w') as z:
    info=zipfile.ZipInfo(filename);info.external_attr=mode<<16;z.writestr(info,b'/etc/passwd')
   with self.assertRaises(bootstrap.SetupError):bootstrap.unzip(archive,self.root/'sdk')
  self.assertFalse((self.root/'escape').exists())
 def test_sdk_extract_preserves_execution_bits(self):
  archive=self.root/'sdk.zip'
  with zipfile.ZipFile(archive,'w') as z:
   info=zipfile.ZipInfo('android/bin/tool');info.external_attr=0o100755<<16;z.writestr(info,b'code')
  bootstrap.unzip(archive,self.root/'sdk',True)
  self.assertTrue((self.root/'sdk/bin/tool').stat().st_mode&0o111)
 def test_sdk_selects_exact_base_platform(self):
  xml='''<repository><license id="sdk">license</license><remotePackage path="platforms;android-36"><uses-license ref="sdk"/><archives><archive><complete><url>platform-36-ext19_r01.zip</url><checksum>ignored</checksum></complete></archive><archive><complete><url>platform-36_r02.zip</url><checksum>correct-platform</checksum></complete></archive></archives></remotePackage><remotePackage path="build-tools;36.0.0"><uses-license ref="sdk"/><archives><archive><host-os>linux</host-os><complete><url>build-tools_r36_linux.zip</url><checksum>correct-tools</checksum></complete></archive></archives></remotePackage></repository>'''
  packages=bootstrap.sdk_packages(xml);self.assertEqual(len(packages),2);self.assertEqual({p['sha1'] for p in packages},{'correct-platform','correct-tools'})
 def test_private_tools_use_one_rustup_sysroot(self):
  text=(ROOT/'bootstrap.py').read_text();self.assertIn("'RUSTUP_HOME':str(rustup)",text);self.assertIn("'RUSTUP_TOOLCHAIN':toolchain",text)
  with self.assertRaises(bootstrap.SetupError):bootstrap.ensure_rust(self.root,'stable; echo bad')
 def test_key_zip_is_read_without_extracting_paths(self):
  archive=self.root/'keys.zip'
  with zipfile.ZipFile(archive,'w') as z:z.writestr('../../secret.jks',b'key data')
  folder=self.root/'private';folder.mkdir();result=lucy.key_input(archive,folder)
  self.assertEqual(result.read_bytes(),b'key data');self.assertTrue(result.is_relative_to(folder));self.assertFalse((self.root/'secret.jks').exists())
 def test_ambiguous_key_zip_is_rejected(self):
  archive=self.root/'keys.zip'
  with zipfile.ZipFile(archive,'w') as z:z.writestr('first.jks',b'key');z.writestr('second.p12',b'key')
  with self.assertRaises(lucy.BuildFailure):lucy.key_input(archive,self.root)
 def test_current_revisions_validate_without_shell(self):
  heads={name:'a'*40 for name in lucy.pipeline.REPOS};self.assertEqual(lucy.pipeline.validate_heads(heads),heads)
  for wrong in [{},{**heads,'wordcraft':'main;touch /tmp/bad'}]:
   with self.assertRaises(lucy.pipeline.BuildError):lucy.pipeline.validate_heads(wrong)
 def test_repeat_freezes_heads_fonts_and_catalogs_without_network(self):
  base=json.loads((lucy.pipeline.TEMPLATE/'engine-lock.json').read_text());prior={'schema':1,'heads':{name:'a'*40 for name in lucy.pipeline.REPOS},'engine_lock':copy.deepcopy(base)}
  prior['engine_lock']['fonts']['source_commit']='b'*40
  with patch.object(lucy.pipeline,'latest',side_effect=AssertionError('Must not refresh main')):
   result=lucy.repeat_snapshot(base,prior,'0'*32)
  self.assertEqual(result['heads'],prior['heads']);self.assertEqual(result['engine_lock']['fonts']['source_commit'],'b'*40)
  self.assertEqual(result['engine_lock']['translations']['files'],prior['engine_lock']['translations']['files'])
  self.assertEqual(result['engine_lock']['engines'][3]['adapter_base_commit'],base['engines'][3]['source_commit'])
  with self.assertRaises(lucy.BuildFailure):lucy.repeat_snapshot(base,None,'0'*32)
  prior['engine_lock']['translations']['files']['../foreign.tsv']='a'*64
  with self.assertRaises(lucy.BuildFailure):lucy.repeat_snapshot(base,prior,'0'*32)
 def test_template_has_no_old_binary_or_key(self):
  template=self.root/'template';(template/'app/src/main/assets/engines').mkdir(parents=True);(template/'app/src/main/assets/engines/old.wasm').write_bytes(b'old')
  (template/'.cache').mkdir();(template/'.cache/key.jks').write_bytes(b'key');(template/'source.rs').write_text('source')
  with patch.object(lucy.pipeline,'TEMPLATE',template):lucy.pipeline.copy_template(self.root/'clean')
  self.assertTrue((self.root/'clean/source.rs').exists());self.assertFalse((self.root/'clean/app/src/main/assets/engines').exists());self.assertFalse((self.root/'clean/.cache').exists())
 def test_failed_packaging_preserves_previous_apk(self):
  out=lucy.output_root(self.root/'out');old=out/'builds/previous';old.mkdir(parents=True);(old/'Lucy.apk').write_bytes(b'old signed apk')
  (out/'latest').symlink_to('builds/previous');(out/'Lucy.apk').symlink_to('latest/Lucy.apk')
  state=self.root/'state';(state/'work').mkdir(parents=True)
  with patch.object(lucy.pipeline,'assemble',side_effect=lucy.pipeline.BuildError('compile stopped')):
   with self.assertRaises(lucy.pipeline.BuildError):lucy.publish({},self.root/'artifacts',state,out,self.root/'sdk',self.root/'key',self.root/'pass',self.root/'log')
  self.assertEqual((out/'Lucy.apk').read_bytes(),b'old signed apk');self.assertEqual((out/'latest').readlink(),Path('builds/previous'))
 def test_failed_compile_retries_with_a_fresh_result_directory(self):
  base=json.loads((lucy.pipeline.TEMPLATE/'engine-lock.json').read_text());engine=base['engines'][0]
  snapshot={'version_name':'test','engine_lock':{**base,'engines':[engine]}}
  state=self.root/'state';work=state/'work/engines/wordcraft';(work/'lucy').mkdir(parents=True);(work/'sources').mkdir()
  (work/'output').mkdir();(work/'output/stale').write_text('incomplete old output');attempts=[]
  def compile(snapshot,name,attempt,target):
   attempts.append(attempt);out=attempt/'output';out.mkdir();self.assertEqual((attempt/'sources').resolve(),(work/'sources').resolve())
   if len(attempts)==1:(out/'partial').write_text('partial');raise lucy.pipeline.BuildError('interrupted')
   (out/'engine').mkdir();lucy.save_json(out/'engine/folio-engine.json',{'folio_version':'test'});return out
  with patch.object(lucy.pipeline,'compile_prepared',side_effect=compile):
   with self.assertRaises(lucy.pipeline.BuildError):lucy.compile_all(snapshot,{'wordcraft':work},state,'test compiler',1)
   result=lucy.compile_all(snapshot,{'wordcraft':work},state,'test compiler',1)
  self.assertNotEqual(attempts[0],attempts[1]);self.assertFalse((result/'wordcraft/partial').exists());self.assertFalse((result/'wordcraft/stale').exists())

class DistributionTests(unittest.TestCase):
 def test_self_extractor_preserves_terminal_and_piped_input(self):
  # The embedded Python program occupies stdin during extraction. The actual
  # builder must receive the caller's original stdin, including its TTY status.
  import shutil,pty
  with tempfile.TemporaryDirectory(prefix='lucy distribution ') as name:
   root=Path(name);shutil.copyfile(ROOT/'build_distribution.py',root/'build_distribution.py')
   (root/'lucy.py').write_text("import sys\nprint('TTY='+str(sys.stdin.isatty()),flush=True)\nprint('ANSWER='+input(),flush=True)\n")
   (root/'password.txt').write_text('not release material');(root/'Lucy-output').mkdir();(root/'Lucy-output/old-source.zip').write_bytes(b'old archive')
   private=root/'pipeline/local-state';private.mkdir(parents=True);(private/'build.lock').touch();(private/'password.txt').write_text('private')
   subprocess.run([sys.executable,str(root/'build_distribution.py')],check=True,stdout=subprocess.DEVNULL)
   with zipfile.ZipFile(root/'dist/Lucy-Builder-Linux-1.0.0.zip') as z:
    self.assertFalse(any('password.txt' in n or 'Lucy-output' in n or 'local-state' in n for n in z.namelist()))
   script=root/'dist/Lucy-Builder-Linux-1.0.0.run'
   result=subprocess.run(['bash',str(script)],input='piped answer\n',capture_output=True,text=True,timeout=15,check=True)
   self.assertIn('TTY=False',result.stdout);self.assertIn('ANSWER=piped answer',result.stdout)
   master,slave=pty.openpty()
   try:
    process=subprocess.Popen(['bash',str(script)],stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    os.write(master,b'terminal answer\n');stdout,stderr=process.communicate(timeout=15)
    self.assertEqual(process.returncode,0,stderr);self.assertIn('TTY=True',stdout);self.assertIn('ANSWER=terminal answer',stdout)
   finally:os.close(master);os.close(slave)

class IdentityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.java=bootstrap.valid_java(__import__('shutil').which('java'))
  if not self.java:self.skipTest('Needs a JDK for actual keytool integration')
 def tearDown(self):self.temp.cleanup()
 def args(self,**extra):
  from types import SimpleNamespace
  return SimpleNamespace(import_key=None,import_password_env=None,key_alias=None,**extra) if not extra else SimpleNamespace(**{'import_key':None,'import_password_env':None,'key_alias':None,**extra})
 def test_identity_is_reused_and_keys_are_private(self):
  key,password=lucy.ensure_identity(self.root,dict(os.environ),self.java,self.args());before=bootstrap.digest(key)
  again,_=lucy.ensure_identity(self.root,dict(os.environ),self.java,self.args());self.assertEqual(bootstrap.digest(again),before);self.assertEqual(password.stat().st_mode&0o777,0o600)
 def test_jks_import_preserves_certificate_and_failure_preserves_identity(self):
  old=self.root/'previous.jks';scope={**os.environ,'TEST_IMPORT_PASSWORD':'android'};kt=self.java/'bin/keytool'
  subprocess.run([str(kt),'-genkeypair','-storetype','JKS','-keystore',str(old),'-alias','folio-preview','-storepass:env','TEST_IMPORT_PASSWORD','-keypass:env','TEST_IMPORT_PASSWORD','-keyalg','RSA','-keysize','2048','-validity','365','-dname','CN=Previous Lucy','-noprompt'],env=scope,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
  with patch.dict(os.environ,{'TEST_IMPORT_PASSWORD':'android'}):key,password=lucy.ensure_identity(self.root,dict(os.environ),self.java,self.args(import_key=old,import_password_env='TEST_IMPORT_PASSWORD'))
  def cert(path,passvalue,alias):
   env={**os.environ,'TEST_PASS':passvalue}
   return subprocess.check_output([str(kt),'-exportcert','-keystore',str(path),'-storepass:env','TEST_PASS','-alias',alias],env=env,stderr=subprocess.DEVNULL)
  self.assertEqual(hashlib.sha256(cert(old,'android','folio-preview')).hexdigest(),hashlib.sha256(cert(key,password.read_text(),'lucy')).hexdigest())
  old_pointer=(self.root/'signing/current').readlink();old_hash=bootstrap.digest(key)
  with patch.dict(os.environ,{'TEST_IMPORT_PASSWORD':'incorrect'}),self.assertRaises(subprocess.CalledProcessError):lucy.ensure_identity(self.root,dict(os.environ),self.java,self.args(import_key=old,import_password_env='TEST_IMPORT_PASSWORD'))
  self.assertEqual((self.root/'signing/current').readlink(),old_pointer);self.assertEqual(bootstrap.digest(key),old_hash)

@unittest.skipUnless(os.environ.get('LUCY_TEST_SDK'),'Set LUCY_TEST_SDK for the official Android signer integration test')
class SignerTests(unittest.TestCase):
 def test_real_pkcs12_signing_uses_the_saved_password_once(self):
  from types import SimpleNamespace
  import shutil
  sdk=Path(os.environ['LUCY_TEST_SDK']).resolve();java=bootstrap.valid_java(shutil.which('java'))
  if not java:self.skipTest('Needs JDK 17 or newer')
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);manifest=root/'AndroidManifest.xml'
   manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.lucy.test"><uses-sdk android:minSdkVersion="26"/><application android:hasCode="false" android:label="Lucy test"/></manifest>')
   unsigned=root/'unsigned.apk';linked=root/'linked.apk';signed=root/'signed.apk';bt=sdk/'build-tools/36.0.0'
   lucy.run([bt/'aapt2','link','-I',sdk/'platforms/android-36/android.jar','--manifest',manifest,'-o',linked])
   lucy.run([bt/'zipalign','-f','4',linked,unsigned])
   key,password=lucy.ensure_identity(root,dict(os.environ),java,SimpleNamespace(import_key=None,import_password_env=None,key_alias=None))
   cert=lucy.sign_apk(sdk,key,password,unsigned,signed)
   der=subprocess.check_output([str(java/'bin/keytool'),'-exportcert','-alias','lucy','-keystore',str(key),'-storepass:env','LUCY_TEST_PASS'],env={**os.environ,'LUCY_TEST_PASS':password.read_text()},stderr=subprocess.DEVNULL)
   self.assertEqual(cert,hashlib.sha256(der).hexdigest());self.assertTrue(signed.is_file())

if __name__=='__main__':unittest.main()
