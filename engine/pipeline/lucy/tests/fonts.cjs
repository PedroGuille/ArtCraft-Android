/* Actual WASM font pickers: process all selected files, not merely FileList[0]. */
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../app/src/main/assets'),out=path.resolve(__dirname,'../build/qa');
const sources=process.env.FOLIO_SOURCE_ROOT||path.resolve(__dirname,'../.cache/sources');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
(async()=>{
 const server=http.createServer((req,res)=>{let p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(p===root)p=path.join(root,'index.html');if(!p.startsWith(root+'/')||!fs.existsSync(p)){res.writeHead(404).end();return;}res.setHeader('Content-Type',p.endsWith('.wasm')?'application/wasm':p.endsWith('.js')?'text/javascript':p.endsWith('.html')?'text/html':p.endsWith('.css')?'text/css':'application/octet-stream');if(process.env.FOLIO_PDF_BASELINE&&p.includes('/engines/pdfcraft/'))p=path.join(process.env.FOLIO_PDF_BASELINE,path.basename(p));fs.createReadStream(p).pipe(res);});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 try{
 let page=await browser.newPage({viewport:{width:1200,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+server.address().port);
 const click=async(x,y)=>{const b=await page.locator('iframe.active-frame').boundingBox();await page.mouse.click(b.x+x,b.y+y);await page.waitForTimeout(300);};
 if(process.env.FOLIO_FONT_ENGINE!=='pdf'){
 await page.locator('#browser-open').setInputFiles(path.join(out,'fixtures','roundtrip.docx'));await page.waitForSelector('#editor-loading.hidden',{state:'attached',timeout:120000});await page.waitForTimeout(1200);
 await click(286,40);await page.screenshot({path:path.join(out,"font-main-picker.png")});
 const choosing=page.waitForEvent('filechooser');await click(370,441);const picker=await choosing;assert.equal(picker.isMultiple(),true,'Word requests a multiple font selection');
 const valid=[path.join(sources,'pdfcraft/assets/fonts/DancingScript.ttf'),path.join(sources,'craft-fonts/fonts/noto-sans-thai/NotoSansThai.ttf')];
 await picker.setFiles([{name:'DancingScript.ttf',mimeType:'font/ttf',buffer:fs.readFileSync(valid[0])},{name:'invalid.ttf',mimeType:'font/ttf',buffer:Buffer.from('not a font')},{name:'NotoSansThai.ttf',mimeType:'font/ttf',buffer:fs.readFileSync(valid[1])}]);
 const word=page.frames().find(f=>f.url().includes('/wordcraft/'));
 const hashes=valid.map(p=>hash(fs.readFileSync(p)));
 await word.waitForFunction(async expected=>{
  const stored=await new Promise((resolve,reject)=>{const r=indexedDB.open('wordcraft',1);r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result,q=db.transaction('fonts').objectStore('fonts').getAll();q.onerror=()=>reject(q.error);q.onsuccess=()=>{db.close();resolve(q.result);};};});
  const actual=await Promise.all(stored.map(async b=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b))).map(x=>x.toString(16).padStart(2,'0')).join('')));
  return expected.every(h=>actual.includes(h));
 },hashes,{timeout:30000,polling:250});
 console.log('PASS: Word imports and persists both valid fonts in one selection, continuing past an invalid middle file');
 assert.deepEqual(errors,[]);await page.screenshot({path:path.join(out,'multi-font-word.png')});await page.close();
 page=await browser.newPage({viewport:{width:1200,height:900}});page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+server.address().port);
 }
 if(process.env.FOLIO_FONT_ENGINE==='word')return;
 await page.locator('#browser-open').setInputFiles(path.join(out,'fixtures','roundtrip.pdf'));await page.waitForSelector('#editor-loading.hidden',{state:'attached',timeout:120000});await page.waitForTimeout(1400);
 await click(277,12);await click(480,156);await click(244,130);
 const choosingPdf=page.waitForEvent('filechooser');await click(65,316);const pdfPicker=await choosingPdf;
 assert.equal(pdfPicker.isMultiple(),true,'PDF requests a multiple font selection');
 await pdfPicker.setFiles([]);
 assert.equal(await page.locator('.document-tab').count(),1,'Cancelling a font selection keeps the document open');
 await click(244,130);const choosingAgain=page.waitForEvent('filechooser');await click(65,316);const batchPicker=await choosingAgain;
 const pdfFonts=[path.join(sources,'pdfcraft/assets/fonts/Inter-Regular.ttf'),path.join(sources,'pdfcraft/assets/fonts/Inter-Medium.ttf')];
 await batchPicker.setFiles([{name:'Inter-Regular.ttf',mimeType:'font/ttf',buffer:fs.readFileSync(pdfFonts[0])},{name:'invalid.ttf',mimeType:'font/ttf',buffer:Buffer.from('not a font')},{name:'Inter-Medium.ttf',mimeType:'font/ttf',buffer:fs.readFileSync(pdfFonts[1])}]);
 await page.waitForTimeout(1800);await page.screenshot({path:path.join(out,'multi-font-pdf.png')});
 await page.locator('#tabs-add').click();await page.locator('#editor-back').click();await page.waitForTimeout(300);
 const downloading=page.waitForEvent('download');await page.locator('#tabs-add').click();await page.locator('#editor-save').click();await (await downloading).saveAs(path.join(out,'multi-font.pdf'));
 assert.deepEqual(errors,[]);console.log('PASS: PDF multi-file font selection and export complete; verify both embedded faces with tests/verify_fonts.py');await page.close();
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
