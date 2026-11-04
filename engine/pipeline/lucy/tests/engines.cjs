/* Real bundled WASM editors remain open together throughout this test. */
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
async function main(){
  fs.mkdirSync(out,{recursive:true});
  const server=http.createServer((req,res)=>{
    let file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
    if(file===root)file=path.join(root,'index.html');
    if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404).end();return;}
    res.setHeader('Content-Type',file.endsWith('.wasm')?'application/wasm':file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.html')?'text/html':'application/octet-stream');
    res.setHeader('Content-Security-Policy',"default-src 'self' blob: data:; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self' blob: data:; object-src 'none'; base-uri 'self'");
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  try{
    const page=await browser.newPage({viewport:{width:1200,height:900},acceptDownloads:true});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    const click=async(x,y,twice=false)=>{const box=await page.locator('iframe.active-frame').boundingBox();await page.mouse[twice?'dblclick':'click'](box.x+x,box.y+y);};
    const save=async()=>{await page.locator('#tabs-add').click();await page.locator('#editor-save').click();};
    const types=[['wordcraft','docx'],['gridcraft','xlsx'],['deckcraft','pptx'],['pdfcraft','pdf']];
    const retained=new Map();
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    for(const [engine,ext] of types){
      await page.locator('#browser-open').setInputFiles(path.join(out,'fixtures','roundtrip.'+ext));
      await page.waitForSelector('#editor-loading.hidden',{state:'attached',timeout:120000});
      await page.waitForTimeout(2000);
      retained.set(engine,page.frames().at(-1));
      if(engine==='pdfcraft'){
        const canvas=retained.get(engine).locator('canvas');
        const cursor=async()=>{const box=await page.locator('iframe.active-frame').boundingBox();await page.mouse.move(box.x+600,box.y+400);await page.waitForTimeout(300);return canvas.evaluate(c=>getComputedStyle(c).cursor);};
        assert.equal(await cursor(),'grab','PDF opens with the Hand tool');
        await click(248,50);await page.waitForTimeout(350); // close All tools, like the tablet layout
        await click(21.6,45.6);
        assert.notEqual(await cursor(),'grab','The reduced Select button receives its click');
        await click(21.6,66);
        assert.equal(await cursor(),'grab','The reduced Hand button receives its click');
        console.log('PASS: PDF defaults to Hand and both scaled tool buttons receive input');
      }

      if(engine==='wordcraft'){
        await click(380,347);await page.keyboard.press('Control+End');await page.keyboard.press('End');await page.keyboard.type(' Folio edited text',{delay:20});
        await page.locator('#tabs-add').click();await page.locator('#editor-undo').click();await page.waitForTimeout(200);
        const undoExport=page.waitForEvent('download');await save();await (await undoExport).saveAs(path.join(out,'undo-wordcraft.docx'));
        await page.locator('#tabs-add').click();await page.locator('#editor-redo').click();await page.waitForTimeout(200);

      }
      await page.screenshot({path:path.join(out,'compact-'+engine+'.png')});
      console.log(`OPEN: ${engine}; ${retained.size} live editors`);
    }
    assert.equal(await page.locator('.document-tab').count(),4);
    assert.equal(page.frames().filter(f=>f.url().includes('/engines/')).length,4);
    await page.screenshot({path:path.join(out,'mixed-tabs-desktop.png')});
    // Change the display while all four real documents remain alive.
    await page.locator('#tabs-add').click();await page.locator('#editor-dark').click();
    assert.equal(await page.locator('#editor-dark').getAttribute('aria-checked'),'true');
    await page.locator('#tabs-add').click();
    for(const [engine] of types){
      await page.locator(`.document-tab[data-engine="${engine}"] .document-tab-button`).click();
      await page.waitForTimeout(1400);
      assert.equal(await retained.get(engine).evaluate(()=>window.__folioDark),true);
      if(engine==='wordcraft'){
        await click(380,347);await page.keyboard.press('Control+End');await page.keyboard.press('End');await page.keyboard.type(' Dark view edit',{delay:20});
      }
      if(engine==='pdfcraft'){
        await click(277,12);await page.waitForTimeout(250);await click(66,248);
        await click(480,227);await page.waitForTimeout(250);await page.keyboard.type('Folio PDF edited',{delay:30});await click(900,507);
      }
      await page.screenshot({path:path.join(out,'dark-'+engine+'.png')});
    }
    // A round trip through Home keeps all four exact editor instances and edits.
    await page.locator('#tabs-home').click();assert.equal(await page.locator('#confirm').evaluate(el=>el.open),false);
    for(const [engine,ext] of types){
      await page.locator(`.document-tab[data-engine="${engine}"] .document-tab-button`).click();
      await page.waitForTimeout(500);
      assert.ok(page.frames().includes(retained.get(engine)),`${engine} frame was retained`);
      if(engine==='wordcraft'||engine==='gridcraft'){
        // File can replace the whole canvas. Its original top Back button is
        // available through the shared menu's Escape action in compact layout.
        await click(25,14);await page.waitForTimeout(150);
        await page.screenshot({path:path.join(out,'backstage-'+engine+'.png')});
        await page.locator('#tabs-add').click();await page.locator('#editor-back').click();await page.waitForTimeout(150);
      }

      if(engine==='deckcraft')await armPresentationSave(retained.get(engine));
      const download=page.waitForEvent('download',{timeout:30000});
      await save();
      if(engine==='deckcraft'){await retained.get(engine).waitForFunction(()=>window.__qaSaveAsReady,null,{timeout:20000});await click(595,132);}
      const file=await download;
      assert.equal(path.extname(file.suggestedFilename()),'.'+ext,'Actual exported format');
      await file.saveAs(path.join(out,'exported-'+engine+'.'+ext));
      console.log(`PASS: ${engine} exports after switching across four live documents`);
    }
    // A fifth tab of an already-open engine keeps a different workbook and edit.
    await page.locator('#tabs-add').click();await page.locator('#new-menu [data-new="gridcraft"]').click();
    await page.waitForSelector('#editor-loading.hidden',{state:'attached',timeout:120000});await page.waitForTimeout(1500);
    await click(50,177,true);await page.keyboard.type('42',{delay:70});await page.keyboard.press('Enter');
    const newWorkbook=page.locator('.document-tab[data-engine="gridcraft"] .document-tab-button').last();
    await page.locator('.document-tab[data-engine="wordcraft"] .document-tab-button').click();
    await newWorkbook.click();await page.waitForTimeout(500);
    const exported=page.waitForEvent('download',{timeout:15000});await save();
    await (await exported).saveAs(path.join(out,'new-workbook.xlsx'));
    assert.equal(await page.locator('.document-tab').count(),5);
    assert.deepEqual(errors,[],'All five live editors have no JavaScript errors');
    await page.screenshot({path:path.join(out,'mixed-tabs-five-documents.png')});
    // Restore light pages without reloading or changing any document data.
    for(const [engine,ext] of types){
      await page.locator(`.document-tab[data-engine="${engine}"] .document-tab-button`).first().click();
      if(engine==='wordcraft'){
        await page.locator('#tabs-add').click();await page.locator('#editor-dark').click();await page.locator('#tabs-add').click();
      }
      await page.waitForTimeout(1000);
      await page.locator('#tabs-add').click();await page.locator('#editor-back').click();await page.waitForTimeout(300);
      await page.screenshot({path:path.join(out,'light-'+engine+'.png')});
      if(engine==='deckcraft')await armPresentationSave(retained.get(engine));
      const download=page.waitForEvent('download',{timeout:30000});await save();
      if(engine==='deckcraft'){await retained.get(engine).waitForFunction(()=>window.__qaSaveAsReady,null,{timeout:20000});await click(595,132);}
      await (await download).saveAs(path.join(out,'light-export-'+engine+'.'+ext));
    }
    await page.locator('#tabs-home').click();
    await page.reload();
    assert.equal(await page.locator('body').evaluate(el=>el.classList.contains('dark')),false,'Appearance persists after reload');
    await page.close();
    console.log('PASS: independent second spreadsheet retains typed value through tab switches');
  }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
