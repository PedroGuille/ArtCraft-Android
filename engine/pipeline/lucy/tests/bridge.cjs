/* Observable host/adapter integration tests. npm install in tests/ before running. */
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../app/src/main/assets');
async function main(){
  const server=http.createServer((req,res)=>{
    const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
    const target=file===root?path.join(root,'index.html'):file;
    if(!target.startsWith(root+path.sep)||!fs.existsSync(target)){res.writeHead(404).end();return;}
    res.setHeader('Content-Type',target.endsWith('.js')?'text/javascript':target.endsWith('.css')?'text/css':target.endsWith('.html')?'text/html':'application/octet-stream');
    fs.createReadStream(target).pipe(res);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox','--disable-dev-shm-usage']});
  try{
    const context=await browser.newContext();
    const page=await context.newPage();
    await page.addInitScript(()=>{
      if(window!==top)return;
      window.recorded={saves:{},cancel:false,hold:false,posts:[],recoveryItems:[]};
      window.AndroidFolio={
        post(json){const m=JSON.parse(json);recorded.posts.push(m);if(m.type==='ready'||m.type==='recoveries')setTimeout(()=>FolioNative.onEvent({type:'recoveries',items:recorded.recoveryItems}),0);},
        beginSave(json){const metadata=JSON.parse(json),id=crypto.randomUUID();recorded.saves[id]={...metadata,bytes:[],chunks:0};return JSON.stringify({id});},
        appendSave(id,encoded){const entry=recorded.saves[id];for(const byte of atob(encoded))entry.bytes.push(byte.charCodeAt(0));entry.chunks++;return true;},
        finishSave(id){if(recorded.hold)return true;const saved=!recorded.cancel;setTimeout(()=>{FolioNative.onEvent({type:'saveResult',id,saved,recovery:true,message:saved?'Guardado':'Exportación cancelada. Hay una copia disponible en Copias guardadas.'});},15);return true;},
        abortSave(id){delete recorded.saves[id];},readClipboard(){return 'Android clipboard';},writeClipboard(text){recorded.clipboard=text;}
      };
    });
    await page.route('**/engines/*/index.html?*',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><script src="../../engine-adapter.js"></script></head><body><canvas id="test_canvas"></canvas><script>dispatchEvent(new CustomEvent("TrunkApplicationStarted"));</script></body></html>'}));
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    assert.equal(await page.locator('#workspace button').count(),2,'Home has exactly Open and Create');
    assert.equal(await page.locator('.sidebar,.intro,.tool-card,.files-section,.home-footer,#search').count(),0,'Old home content is removed');
    await page.locator('#open-top').click();
    assert.ok(await page.evaluate(()=>recorded.posts.some(m=>m.type==='open')),'Home Open invokes Android picker');
    await page.locator('#create-file').click();
    assert.deepEqual(await page.locator('#create-dialog [data-new]').allTextContents(),['WDocumento','XHoja de cálculo','PPresentación','PDFPDF']);
    assert.equal(await page.locator('.document-tab').count(),0,'Opening Create does not start an editor');
    await page.evaluate(()=>FolioNative.back());
    assert.equal(await page.locator('#create-dialog').evaluate(d=>d.open),false,'Android Back dismisses Create');
    await page.locator('#create-file').click();
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#create-dialog').evaluate(d=>d.open),false,'Escape dismisses Create');
    await page.locator('#create-file').click();
    await page.locator('#create-dialog [data-new="wordcraft"]').click();
    await page.waitForSelector('#editor-loading.hidden',{state:'attached'});
    const frame=page.frames().find(f=>f.url().includes('/engines/'));
    assert.equal(await page.locator('.editor-toolbar').count(),0,'No separate host toolbar');
    const geometry=await page.evaluate(()=>{
      const stage=document.getElementById('editor-stage').getBoundingClientRect();
      const frame=document.querySelector('iframe.active-frame').getBoundingClientRect();
      return {stageTop:stage.top,tabBottom:document.getElementById('document-bar').getBoundingClientRect().bottom,frameTop:frame.top,frameBottom:frame.bottom,stageBottom:stage.bottom};
    });
    assert.equal(geometry.stageTop,geometry.tabBottom,'Editor begins immediately below document tabs');
    assert.equal(geometry.stageTop,24,'Document tabs use half the previous height');
    assert.equal(geometry.stageTop-geometry.frameTop,0,'No cropped editor canvas');
    assert.ok(Math.abs(geometry.frameBottom-geometry.stageBottom)<1,'Full visible height belongs to the editor');
    await page.evaluate(()=>{recorded.recoveryItems=[{id:'sample',name:'<b>saved.docx</b>',size:123,time:0}];FolioNative.onEvent({type:'recoveries',items:recorded.recoveryItems});});
    await page.locator('#tabs-add').click();await page.locator('#show-recoveries').click();
    assert.equal(await page.locator('#recoveries-dialog').evaluate(d=>d.open),true,'Saved copies is available from the existing menu');
    assert.equal(await page.locator('.recovery-open strong').textContent(),'<b>saved.docx</b>','Saved names remain literal text');
    assert.equal(await page.locator('#recovery-list b').count(),0);
    await page.locator('.file-action').first().click();
    assert.ok(await page.evaluate(()=>recorded.posts.some(m=>m.type==='share'&&m.id==='sample')));
    await page.evaluate(()=>FolioNative.back());
    assert.equal(await page.locator('#recoveries-dialog').evaluate(d=>d.open),false);
    assert.equal(await page.locator('#editor').isVisible(),true,'Closing Saved copies keeps the current editor');
    await frame.evaluate(()=>{window.menuKeys=[];document.addEventListener('keydown',event=>{if(event.ctrlKey)menuKeys.push(event.key);});});
    await page.locator('#tabs-add').click();await page.locator('#editor-undo').click();
    await frame.waitForFunction(()=>window.menuKeys.includes('z'));
    await page.locator('#tabs-add').click();await page.locator('#editor-redo').click();
    await frame.waitForFunction(()=>window.menuKeys.includes('y'));
    assert.equal(await page.locator('#new-menu').isVisible(),false,'Editor command dismisses existing menu');

    // PdfCraft's actual synchronous anchor-click-then-revoke ordering.
    await frame.evaluate(()=>{
      const bytes=Uint8Array.from({length:170003},(_,i)=>(i*73)%256),url=URL.createObjectURL(new Blob([bytes]));
      const a=document.createElement('a');a.download='roundtrip.pdf';a.href=url;a.click();URL.revokeObjectURL(url);
    });
    await page.waitForFunction(()=>document.getElementById('toast').textContent==='Copia guardada.');
    const saved=await page.evaluate(()=>Object.values(recorded.saves)[0]);
    assert.equal(saved.size,170003);assert.equal(saved.chunks,3);
    assert.deepEqual(saved.bytes,Array.from({length:170003},(_,i)=>(i*73)%256));
    // A same-origin message from the wrong window must not invoke the Android bridge.
    await page.evaluate(()=>window.postMessage({type:'folio:save',name:'spoof.pdf',blob:new Blob(['bad'])},location.origin));
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(()=>Object.keys(recorded.saves).length),1);
    await page.evaluate(()=>recorded.cancel=true);
    await frame.evaluate(()=>{const a=document.createElement('a');a.download='cancelled.pdf';a.href=URL.createObjectURL(new Blob(['kept recovery']));a.click();URL.revokeObjectURL(a.href);});
    await page.waitForFunction(()=>document.getElementById('toast').textContent.includes('Exportación cancelada'));
    assert.equal(await page.evaluate(()=>Object.keys(recorded.saves).length),2);
    // Home and opening another type never unload or prompt for the first editor.
    await frame.evaluate(()=>{window.documentState={text:'unsaved word',selection:7};window.ticks=0;function tick(){window.ticks++;requestAnimationFrame(tick);}requestAnimationFrame(tick);});
    await page.locator('#tabs-home').click();
    assert.equal(await page.locator('#confirm').evaluate(el=>el.open),false);
    assert.equal(await page.locator('#workspace').isVisible(),true);
    assert.equal(await page.locator('#document-tabs [role="tab"]').count(),1);
    await page.locator('.document-tab-button').first().click();
    for(const engine of ['gridcraft','deckcraft','pdfcraft']){
      await page.locator('#tabs-home').click();
      await page.locator('#create-file').click();
      await page.locator(`#create-dialog [data-new="${engine}"]`).click();
      await page.waitForSelector('#editor-loading.hidden',{state:'attached'});
    }
    assert.equal(page.frames().filter(f=>f.url().includes('/engines/')).length,4);
    assert.equal(await page.locator('.document-tab').count(),4);
    await page.locator('#tabs-add').click();await page.locator('#editor-dark').click();await page.locator('#tabs-add').click();
    for(const editor of page.frames().filter(f=>f.url().includes('/engines/'))){
      await editor.waitForFunction(()=>window.__folioDark===true,null,{polling:50});
    }
    assert.equal(await page.evaluate(()=>recorded.posts.filter(m=>m.type==='appearance').at(-1).dark),true,'Native system bars follow the display mode');
    const ticks=await frame.evaluate(()=>window.ticks);
    await page.waitForTimeout(120);
    assert.equal(await frame.evaluate(()=>window.ticks),ticks,'Inactive editor animation is paused');
    await page.locator('.document-tab-button').first().click();
    await page.waitForTimeout(100);
    assert.ok(await frame.evaluate(()=>window.ticks)>ticks,'Resuming a tab restarts its retained animation');
    assert.deepEqual(await frame.evaluate(()=>window.documentState),{text:'unsaved word',selection:7});
    // Multi-window resizing changes the available WebView viewport without
    // unloading the open document sessions or leaving unused host bands.
    for (const viewport of [{width:680,height:800},{width:340,height:432},{width:1280,height:720}]) {
      await page.setViewportSize(viewport);
      const resized=await page.evaluate(()=>{
        const bar=document.getElementById('document-bar').getBoundingClientRect();
        const stage=document.getElementById('editor-stage').getBoundingClientRect();
        const editor=document.querySelector('iframe.active-frame').getBoundingClientRect();
        return {barBottom:bar.bottom,stageTop:stage.top,editorTop:editor.top,editorBottom:editor.bottom,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth};
      });
      assert.equal(resized.stageTop,resized.barBottom,'Resized editor follows tabs');
      assert.equal(resized.editorTop,resized.stageTop,'Resizing adds no top band');
      assert.ok(Math.abs(resized.editorBottom-resized.height)<1,'Editor fills the resized viewport');
      assert.equal(resized.overflow,false,'No horizontal overflow in split-size viewports');
      assert.equal(page.frames().filter(f=>f.url().includes('/engines/')).length,4,'All editors survive resizing');
      assert.deepEqual(await frame.evaluate(()=>window.documentState),{text:'unsaved word',selection:7});
    }
    // A queued export belongs to its originating tab, even after switching away.
    await page.evaluate(()=>{recorded.cancel=false;recorded.hold=true;});
    await frame.evaluate(async()=>{
      const handle=await showSaveFilePicker({suggestedName:'retained.docx'}),writer=await handle.createWritable();
      await writer.write('retained document bytes');window.exportResult='pending';writer.close().then(()=>window.exportResult='saved',()=>window.exportResult='failed');
    });
    await page.waitForFunction(()=>Object.keys(recorded.saves).length===3);
    await page.locator('.document-tab-button').last().click();
    await page.locator('.document-tab-close').first().click();
    assert.equal(await page.locator('#confirm').evaluate(el=>el.open),false,'An exporting tab cannot be destroyed');
    await page.evaluate(()=>{const id=Object.keys(recorded.saves).at(-1);FolioNative.onEvent({type:'saveResult',id,saved:true});recorded.hold=false;});
    await frame.waitForFunction(()=>window.exportResult==='saved',null,{polling:50});
    assert.equal(await page.locator('.document-tab-name').first().textContent(),'retained.docx');
    assert.equal(await page.locator('.document-tab.is-active').getAttribute('data-engine'),'pdfcraft');
    // Duplicate editor types are independent sessions; closing a background tab
    // leaves the current document and the other three editors intact.
    await page.locator('#tabs-add').click();await page.locator('#new-menu [data-new="wordcraft"]').click();
    await page.waitForSelector('#editor-loading.hidden',{state:'attached'});
    assert.equal(await page.locator('.document-tab').count(),5);
    assert.equal(await page.locator('.document-tab-name').last().textContent(),'Documento 2.docx');
    await page.locator('.document-tab[data-engine="gridcraft"] .document-tab-close').click();
    await page.waitForSelector('#confirm[open]');await page.locator('#keep-editing').click();
    assert.equal(await page.locator('.document-tab').count(),5);
    await page.locator('.document-tab[data-engine="gridcraft"] .document-tab-close').click();await page.locator('#close-editor').click();
    assert.equal(await page.locator('.document-tab').count(),4);
    assert.equal(await page.locator('.document-tab.is-active .document-tab-name').textContent(),'Documento 2.docx');
    // Reopening the same native URI focuses its existing unsaved session.
    await page.evaluate(()=>FolioNative.onEvent({type:'opened',name:'same.docx',uri:'content://tests/same',url:location.origin+'/templates/blank.docx'}));
    await page.waitForSelector('#editor-loading.hidden',{state:'attached'});
    await page.evaluate(()=>FolioNative.onEvent({type:'opened',name:'same.docx',uri:'content://tests/same',url:location.origin+'/templates/blank.docx?duplicate'}));
    assert.equal(await page.locator('.document-tab').count(),5);
    assert.ok(await page.evaluate(()=>recorded.posts.some(m=>m.type==='releaseDocument'&&m.url.endsWith('?duplicate'))));
    await page.evaluate(()=>FolioNative.back());
    assert.equal(await page.locator('#workspace').isVisible(),true);
    await page.evaluate(()=>{FolioNative.back();});await page.waitForSelector('#confirm[open]');
    await page.locator('#keep-editing').click();
    assert.equal(await page.evaluate(()=>recorded.posts.some(m=>m.type==='exit')),false);
    await page.evaluate(()=>{FolioNative.back();});await page.locator('#close-editor').click();
    assert.equal(await page.evaluate(()=>recorded.posts.some(m=>m.type==='exit')),true);
    await page.reload();
    assert.equal(await page.locator('body').evaluate(el=>el.classList.contains('dark')),true,'Dark mode persists between launches');
    assert.equal(await page.locator('#about, #about-dialog').count(),0,'Removed About UI is absent');
    await context.close();
    const mobile=await browser.newPage({viewport:{width:412,height:915},isMobile:true,hasTouch:true,locale:'es-UY'});
    await mobile.route('**/engines/*/index.html?*',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><script src="../../engine-adapter.js"></script></head><body><canvas id="test_canvas"></canvas><script>dispatchEvent(new CustomEvent("TrunkApplicationStarted"));</script></body></html>'}));
    await mobile.goto(`http://127.0.0.1:${server.address().port}`);
    assert.equal(await mobile.locator('#open-top').textContent(),'Abrir archivos');
    assert.equal(await mobile.locator('#create-file').textContent(),'Crear archivo');
    assert.equal(await mobile.locator('#workspace button').count(),2);
    await mobile.locator('#create-file').click();
    await mobile.locator('#create-dialog [data-new="wordcraft"]').click();
    await mobile.waitForSelector('#editor-loading.hidden',{state:'attached'});
    for(const engine of ['gridcraft','deckcraft','pdfcraft']){
      await mobile.locator('#tabs-add').click();await mobile.locator(`#new-menu [data-new="${engine}"]`).click();
      await mobile.waitForSelector('#editor-loading.hidden',{state:'attached'});
    }
    assert.equal(await mobile.locator('.document-tab').count(),4);
    assert.equal(await mobile.locator('#tabs-open').count(),1,'One persistent Open control');
    assert.equal(await mobile.locator('#tabs-open').textContent(),'Abrir un archivo');
    const homeBounds=await mobile.locator('#tabs-home').boundingBox();
    const openBounds=await mobile.locator('#tabs-open').boundingBox();
    const tabsBounds=await mobile.locator('#document-tabs').boundingBox();
    assert.ok(homeBounds.x+homeBounds.width<=openBounds.x,'Open is immediately after Home');
    assert.ok(openBounds.x+openBounds.width<=tabsBounds.x,'Open is before the document tabs');
    const barBounds=await mobile.locator('#document-bar').boundingBox();
    assert.ok(openBounds.height>0&&openBounds.y>=barBounds.y&&openBounds.y+openBounds.height<=barBounds.y+barBounds.height,'Open fits inside the compact strip');
    const choosing=mobile.waitForEvent('filechooser');
    await mobile.locator('#tabs-open').click();
    const picker=await choosing;assert.equal(picker.isMultiple(),true);
    await picker.setFiles([]);
    assert.equal(await mobile.locator('.document-tab').count(),4,'Cancelling Open retains every document');

    assert.equal(await mobile.locator('#editor-save').textContent(),'Guardar copia');
    assert.ok(await mobile.locator('#document-tabs').evaluate(el=>el.scrollWidth>el.clientWidth),'Phone tab strip scrolls');
    await mobile.locator('.document-tab-button').first().click();
    assert.equal(await mobile.locator('.document-tab.is-active').getAttribute('data-engine'),'wordcraft');
    await mobile.locator('.document-tab[data-engine="gridcraft"] .document-tab-close').click();
    await mobile.locator('#keep-editing').click();
    assert.equal(await mobile.locator('.document-tab').count(),4);
    assert.equal(await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await mobile.screenshot({path:path.resolve(__dirname,'../build/qa/mixed-tabs-phone-es.png')});
    await mobile.close();
    console.log('PASS: binary exports, cancellation, source validation, mixed tabs, retained edits, repeated split-size viewport transitions, background routing, close protection, persistent dark mode, compact 24px tabs, minimal two-button home and all four creation options, Spanish mobile layout.');
  }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
