/* Real editor startup and selected-engine host behavior from packaged APK bytes. */
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(process.argv[2]),engine=process.argv[3];
const mime={'.wasm':'application/wasm','.js':'text/javascript','.css':'text/css','.html':'text/html','.json':'application/json','.svg':'image/svg+xml'};
(async()=>{
 const server=http.createServer((req,res)=>{
  let file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(file===root)file=path.join(root,'index.html');
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404).end();return;}
  res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');
  res.setHeader('Content-Security-Policy',"default-src 'self' blob: data:; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self' blob: data:; object-src 'none'; base-uri 'self'");
  fs.createReadStream(file).pipe(res);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 try{
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1280,height:850}});const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{window.qaEvents=[];addEventListener('message',event=>{if(event.data?.type)window.qaEvents.push(event.data.type);});});
  await page.goto('http://127.0.0.1:'+server.address().port);
  const selected=JSON.parse(fs.readFileSync(path.join(root,'selection.json'))).engines;
  for(const name of ['wordcraft','pdfcraft','gridcraft','deckcraft'])assert.equal(await page.locator('[data-new="'+name+'"]').count()>0,selected.includes(name));
  await page.locator('#create-file').click();await page.locator('#create-dialog [data-new="'+engine+'"]').click();
  await page.waitForFunction(()=>window.qaEvents.includes('folio:ready'),null,{timeout:180000});
  assert.equal(await page.locator('iframe.active-frame').count(),1);
  await page.waitForTimeout(1600);assert.deepEqual(errors,[]);
  if(engine==='vectorcraft'){
   const fixture=path.join(root,'test.svg');fs.writeFileSync(fixture,'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="80" height="80" fill="red"/></svg>');
   await page.locator('#browser-open').setInputFiles(fixture);
   await page.waitForFunction(()=>window.qaEvents.filter(x=>x==='folio:ready').length===2,null,{timeout:180000});
   await page.waitForTimeout(2500);assert.equal(await page.locator('.document-tab').count(),2);assert.deepEqual(errors,[]);
  }
  await page.screenshot({path:path.join(root,'qa-startup.png')});
  console.log('PASS packaged browser startup',engine,'selection',selected,'real WASM, host readiness and tabs');
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
