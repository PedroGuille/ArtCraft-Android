"""Exercise multi-module PDF packaging without invoking Cargo or the network."""
import hashlib, importlib.util, io, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lucy_web_assets',ROOT/'engine/pipeline/lucy/scripts/build_engines.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)

class WebAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def sources(self,href='../pdfcraft-ocr-worker/Cargo.toml'):
        source=self.root/'source';page=source/'apps/pdfcraft-web';page.mkdir(parents=True)
        (source/'Cargo.lock').write_text('version = 4\n[[package]]\nname = "wasm-bindgen"\nversion = "0.2.105"\n')
        (page/'Cargo.toml').write_text('[package]\nname="pdfcraft-web"\nversion="1.0.0"\n')
        worker=source/'apps/pdfcraft-ocr-worker';worker.mkdir()
        (worker/'Cargo.toml').write_text('[package]\nname="pdfcraft-ocr-worker"\nversion="1.0.0"\n')
        (page/'index.html').write_text('<html><head><link data-trunk rel="rust" href="Cargo.toml"><link data-trunk rel="rust" data-type="worker" href="'+href+'"></head><body>Editor</body></html>')
        return source
    @staticmethod
    def compile_binary(name,manifest,source,env,bindgen,dist):
        (dist/(name+'.js')).write_text("const url = new URL('"+name+"_bg.wasm', import.meta.url);")
        (dist/(name+'_bg.wasm')).write_bytes(b'\0asm'+name.encode())
    def test_pdf_worker_gets_a_hashed_module_loader_and_metadata(self):
        source=self.sources()
        with patch.object(assets,'tool',return_value='wasm-bindgen'),patch.object(assets,'compile_binary',self.compile_binary),patch.object(assets,'pdf_models') as models:
            assets.compile_editor({'id':'pdfcraft'},source,{})
        dist=source/'dist/folio-android';page=(dist/'index.html').read_text()
        self.assertNotIn('rel="rust"',page)
        self.assertIn('TrunkApplicationStarted',page)
        self.assertIn('name="pdfcraft-ocr-worker"',page)
        loader=list(dist.glob('pdfcraft-ocr-worker-*_loader.js'))
        self.assertEqual(len(loader),1)
        self.assertIn('./'+loader[0].name,page)
        glue=list(dist.glob('pdfcraft-ocr-worker-*.js'))
        glue=[p for p in glue if not p.name.endswith('_loader.js')]
        wasm=list(dist.glob('pdfcraft-ocr-worker-*_bg.wasm'))
        self.assertEqual(len(glue),1);self.assertEqual(len(wasm),1)
        self.assertIn(glue[0].name,loader[0].read_text())
        self.assertIn(wasm[0].name,glue[0].read_text())
        models.assert_called_once_with(source,dist)
    def test_worker_manifest_cannot_escape_selected_sources(self):
        source=self.sources('../../../outside/Cargo.toml')
        with patch.object(assets,'tool',return_value='wasm-bindgen'),patch.object(assets,'compile_binary',self.compile_binary),self.assertRaisesRegex(ValueError,'outside'):
            assets.compile_editor({'id':'pdfcraft'},source,{})
    def test_wrong_model_bytes_are_rejected_and_partial_file_removed(self):
        target=self.root/'model.onnx';expected=hashlib.sha256(b'correct model').hexdigest()
        with patch.object(assets.urllib.request,'urlopen',return_value=io.BytesIO(b'incorrect model')),self.assertRaisesRegex(ValueError,'checksum mismatch'):
            assets.verified_download('https://models.example.invalid/test',expected,target)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name+'.part').exists())

if __name__=='__main__':unittest.main()
