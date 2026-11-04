/* Exercise simultaneous real WASM editors and their exports. */
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../app/src/main/assets'),out=path.resolve(__dirname,'../build/qa');
async function armPresentationSave(frame){
 await frame.evaluate(()=>{
  window.__qaSaveAsReady=false;let arrows=0;
  const finished=e=>{if(e.key==='ArrowDown'&&++arrows===5){document.removeEventListener('keyup',finished,true);requestAnimationFrame(()=>requestAnimationFrame(()=>{window.__qaSaveAsReady=true}));}};
  document.addEventListener('keyup',finished,true);
 });
}
(async()=>{
 const server=http.createServer((req,res)=>{let p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(p===root)p=path.join(root,'index.html');if(!p.startsWith(root+'/')||!fs.existsSync(p)){res.writeHead(404).end();return;}res.setHeader('Content-Type',p.endsWith('.wasm')?'application/wasm':p.endsWith('.html')?'text/html':p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':'application/octet-stream');fs.createReadStream(p).pipe(res);});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 try{
 const page=await browser.newPage({viewport:{width:1280,height:900},locale:'es-UY',acceptDownloads:true}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const tab=engine=>page.locator(`.document-tab[data-engine="${engine}"] .document-tab-button`);
 const open=async(engine,file)=>{await page.locator('#browser-open').setInputFiles(path.join(out,'fixtures',file));await page.waitForSelector('#editor-loading.hidden',{state:'attached',timeout:120000});await page.waitForTimeout(1600);const frame=page.frames().find(f=>f.url().includes('/'+engine+'/'));await frame.evaluate(()=>{window.splitIdentity=crypto.randomUUID();window.splitWheels=0;document.addEventListener('wheel',()=>splitWheels++,true)});return frame;};
 const click=async(frame,x,y,twice=false)=>{const element=await frame.frameElement(),box=await element.boundingBox(),scale=await element.evaluate(e=>Number(e.style.transform.match(/scale\(([^)]+)/)[1]));await page.mouse[twice?'dblclick':'click'](box.x+x*scale,box.y+y*scale);};
 const save=async(frame,name,deck=false)=>{if(deck)await armPresentationSave(frame);const download=page.waitForEvent('download',{timeout:45000});await page.locator('#tabs-add').click();await page.locator('#editor-save').click();if(deck){await frame.waitForFunction(()=>window.__qaSaveAsReady,null,{timeout:20000});await click(frame,595,132);}await (await download).saveAs(path.join(out,name));await page.waitForTimeout(250);};
 await page.goto('http://127.0.0.1:'+server.address().port);
 const word=await open('wordcraft','roundtrip.docx'),wordID=await word.evaluate(()=>splitIdentity);
 const pdf=await open('pdfcraft','split-pages.pdf'),pdfID=await pdf.evaluate(()=>splitIdentity);
 await click(pdf,248,50);await tab('wordcraft').click();await page.locator('#tabs-split').click();await page.waitForTimeout(1600);
 assert.equal(await page.locator('iframe.active-frame').count(),2);
 let boxes=await page.locator('iframe.active-frame').evaluateAll(fs=>fs.map(f=>{const r=f.getBoundingClientRect();return{x:r.x,width:r.width,y:r.y,bottom:r.bottom}}));assert.equal(boxes[0].width,640);assert.equal(boxes[1].width,640);assert.equal(boxes[1].x,640);assert.equal(boxes[0].y,24);assert.equal(boxes[0].bottom,900);
 await click(word,320,347);await page.keyboard.press('Control+End');await page.keyboard.press('End');await page.keyboard.type(' Lucy split retained text',{delay:25});
 await click(pdf,400,400);await page.waitForFunction(()=>document.querySelector('.document-tab.is-active')?.dataset.engine==='pdfcraft');const pdfBefore=await pdf.locator('canvas').screenshot();await page.mouse.wheel(0,700);await page.waitForTimeout(900);const pdfAfter=await pdf.locator('canvas').screenshot();assert.notDeepEqual(pdfAfter,pdfBefore,'PDF responds to its own scroll');assert.equal(await word.evaluate(()=>splitWheels),0);assert(await pdf.evaluate(()=>splitWheels)>0);
 await page.screenshot({path:path.join(out,'split-word-pdf.png')});
 await tab('wordcraft').click();await save(word,'split-word.docx');await tab('pdfcraft').click();await save(pdf,'split-pdf.pdf');
 const grid=await open('gridcraft','roundtrip.xlsx'),gridID=await grid.evaluate(()=>splitIdentity);assert.equal(await page.locator('iframe.active-frame').count(),2);
 await click(grid,50,177);await page.keyboard.press('Delete');await page.waitForTimeout(150);await page.keyboard.type('42',{delay:100});await page.keyboard.press('Enter');
 await tab('wordcraft').click();const deck=await open('deckcraft','roundtrip.pptx'),deckID=await deck.evaluate(()=>splitIdentity);assert.equal(await page.locator('iframe.active-frame').count(),2);
 await page.screenshot({path:path.join(out,'split-deck-sheet.png')});
 await save(deck,'split-deck.pptx',true);await tab('gridcraft').click();await save(grid,'split-sheet.xlsx');
 await page.locator('#tabs-add').click();await page.locator('#editor-dark').click();await page.locator('#tabs-add').click();await page.waitForTimeout(800);await page.screenshot({path:path.join(out,'split-dark.png')});for(const f of [word,pdf,grid,deck])assert.equal(await f.evaluate(()=>window.__folioDark),true);
 await page.locator('#tabs-split').click();assert.equal(await page.locator('iframe.active-frame').count(),1);assert.equal((await page.locator('iframe.active-frame').boundingBox()).width,1280);
 await page.locator('#tabs-split').click();assert.equal(await page.locator('iframe.active-frame').count(),2);await page.locator('#tabs-home').click();assert(await page.locator('#workspace').isVisible());await tab('wordcraft').click();assert.equal(await page.locator('iframe.active-frame').count(),2);
 for(const [f,id] of [[word,wordID],[pdf,pdfID],[grid,gridID],[deck,deckID]])assert.equal(await f.evaluate(()=>splitIdentity),id,'Every editor instance survives splitting, replacing views and Home');
 assert.deepEqual(errors,[]);console.log('PASS: real Word/PDF and presentation/spreadsheet pairs, independent PDF scrolling, in-pane edits and four format exports, narrow presentation Save As, dark mode and retained instances after split/unsplit/Home.');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
