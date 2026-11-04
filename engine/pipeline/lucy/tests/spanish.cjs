/* Spanish is fixed even with a foreign browser locale and legacy UI preferences. */
const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../app/src/main/assets'),out=path.resolve(__dirname,'../build/qa');
(async()=>{
 const server=http.createServer((req,res)=>{let p=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(p===root)p=path.join(root,'index.html');if(!p.startsWith(root+'/')||!fs.existsSync(p)){res.writeHead(404).end();return;}res.setHeader('Content-Type',p.endsWith('.wasm')?'application/wasm':p.endsWith('.html')?'text/html':p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':'application/octet-stream');fs.createReadStream(p).pipe(res);});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-dev-shm-usage']});
 try{
  for(const locale of ['en-US','ja-JP']){
   const page=await browser.newPage({locale,viewport:{width:1200,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto('http://127.0.0.1:'+server.address().port);
   assert.equal(await page.locator('html').getAttribute('lang'),'es');assert.equal(await page.locator('#open-top').textContent(),'Abrir archivos');assert.equal(await page.locator('#create-file').textContent(),'Crear archivo');
   await page.evaluate(()=>{localStorage.setItem('gridcraft.ui',JSON.stringify({language:'ja',zoom:125}));localStorage.setItem('gridcraft.prefs',JSON.stringify({r1c1:true,user_name:'Prueba de idioma'}));});
   await page.locator('#create-file').click();assert.deepEqual(await page.locator('#create-dialog [data-new]').allTextContents(),['WDocumento','XHoja de cálculo','PPresentación','PDFPDF']);
   await page.locator('#create-dialog [data-new="gridcraft"]').click();await page.waitForSelector('#editor-loading.hidden',{state:'attached',timeout:120000});
   await page.waitForFunction(()=>JSON.parse(localStorage.getItem('gridcraft.ui')||'{}').language==='es',null,{timeout:15000});
   assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('gridcraft.prefs')).r1c1),true,'Migrating language preserves editing preferences');
   await page.screenshot({path:path.join(out,'spanish-'+locale+'.png')});
   assert.equal(await page.locator('#tabs-split').textContent(),'Dividir');await page.locator('#tabs-split').click();assert.equal(await page.locator('#tabs-split').textContent(),'Desdividir');
   const grid=page.frames().find(f=>f.url().includes('/gridcraft/'));assert.equal(await grid.locator('html').getAttribute('lang'),'es');assert.deepEqual(errors,[]);
   await page.close();console.log('PASS: '+locale+' browser, Spanish UI, legacy Japanese setting migrates to Spanish without resetting r1c1, Spanish split controls');
  }
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
