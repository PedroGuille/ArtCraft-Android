/* Platform adapter for the Lucy WebAssembly editor builds. */
"use strict";
(() => {
  const origin=location.origin;
  window.__folioDark=window.frameElement?.dataset.dark==="true";
  window.__folioReadOnly=window.frameElement?.dataset.readOnly==="true";
  const send=message=>parent.postMessage(message,origin);
  // Keep each WASM editor alive, but stop its animation loop while another tab
  // or Home is visible. Retain callbacks so rendering resumes without a reload.
  let active=window.frameElement?.dataset.active!=="false", nextFrame=1;
  const frames=new Map(), raf=window.requestAnimationFrame.bind(window), caf=window.cancelAnimationFrame.bind(window);
  function schedule(entry) {
    entry.nativeId=raf(time=>{frames.delete(entry.id);entry.callback(time);});
  }
  window.requestAnimationFrame=callback=>{
    const entry={id:nextFrame++,callback};frames.set(entry.id,entry);
    if(active)schedule(entry);
    return entry.id;
  };
  window.cancelAnimationFrame=id=>{
    const entry=frames.get(id);if(entry?.nativeId!==undefined)caf(entry.nativeId);frames.delete(id);
  };
  function setActive(value) {
    if(active===value)return;
    active=value;
    for(const entry of frames.values()) {
      if(active)schedule(entry);
      else {if(entry.nativeId!==undefined)caf(entry.nativeId);delete entry.nativeId;}
    }
  }
  // Both visible documents keep rendering; report which one receives input so
  // the shared file menu and tab switches address that side.
  const reportFocus=()=>{if(active)send({type:"folio:focus"});};
  const reportInteraction=()=>{if(active)send({type:"folio:interact"});};
  document.addEventListener("pointerdown",()=>{reportInteraction();reportFocus();},true);
  document.addEventListener("wheel",reportInteraction,{capture:true,passive:true});
  window.addEventListener("focus",reportFocus);
  window.addEventListener("keydown",event=>{
    if(!active||!event.ctrlKey||event.altKey)return;
    const key=event.key.toLowerCase();
    const message=key==="tab"?{type:"folio:tab-step",direction:event.shiftKey?-1:1}:key==="w"?{type:"folio:close-tab"}:key==="o"?{type:"folio:open-picker"}:null;
    if(message){event.preventDefault();event.stopImmediatePropagation();send(message);}
  },true);
  const pending=new Map(),blobs=new Map();
  const originalCreate=URL.createObjectURL.bind(URL), originalRevoke=URL.revokeObjectURL.bind(URL);
  const create=(blob)=>{const url=originalCreate(blob);blobs.set(url,blob);return url;};
  URL.createObjectURL=create;
  URL.revokeObjectURL=url=>{blobs.delete(url);originalRevoke(url);};
  function requestSave(name,blob) {
    const requestId=crypto.randomUUID();
    return new Promise((resolve,reject)=>{pending.set(requestId,{resolve,reject});send({type:"folio:save",requestId,name,blob});});
  }
  const click=HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click=function() {
    if (this.hasAttribute("download") && (this.href.startsWith("blob:")||this.href.startsWith("data:"))) {
      // Capture the Blob synchronously: PdfCraft revokes the URL immediately after click().
      const blob=blobs.get(this.href),name=this.download||"Documento";
      (blob?Promise.resolve(blob):fetch(this.href).then(response=>response.blob())).then(value=>requestSave(name,value)).catch(error=>send({type:"folio:error",message:error.message}));
      return;
    }
    return click.call(this);
  };
  // WordCraft/GridCraft already use the File System Access API when provided. Resolve only
  // after Android confirms writing, so cancelling a picker cannot masquerade as a saved file.
  window.showSaveFilePicker=async options=>{
    const name=options?.suggestedName||"Documento";
    return {kind:"file",name,async createWritable(){
      let parts=[],closed=false;
      return {
        async write(value){
          if(closed) throw new Error("La exportación está cerrada.");
          if(value&&typeof value==="object"&&value.type==="write") value=value.data;
          if(value&&typeof value==="object"&&(value.type==="seek"||value.type==="truncate")) throw new Error("La exportación con acceso aleatorio no está disponible.");
          parts.push(value);
        },
        async close(){if(closed) return;closed=true;await requestSave(name,new Blob(parts));parts=[];},
        async abort(){closed=true;parts=[];}
      };
    }};
  };
  async function shortcut(key) {
    const canvas=document.querySelector("canvas");if(!canvas)return;
    canvas.focus();
    // Let eframe observe that its iframe regained focus before handing it a shortcut.
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    const target=document.activeElement||canvas;
    // eframe's IME agent treats keyCode 0 as an iOS composition event and consumes it.
    // Supply the standard legacy codes as well as key/code for synthetic toolbar commands.
    const props={key,code:`Key${key.toUpperCase()}`,keyCode:key.toUpperCase().charCodeAt(0),which:key.toUpperCase().charCodeAt(0),ctrlKey:true,bubbles:true,cancelable:true};
    target.dispatchEvent(new KeyboardEvent("keydown",{...props,key:"Control",code:"ControlLeft",keyCode:17,which:17}));
    target.dispatchEvent(new KeyboardEvent("keydown",props));
    requestAnimationFrame(()=>{target.dispatchEvent(new KeyboardEvent("keyup",props));target.dispatchEvent(new KeyboardEvent("keyup",{...props,key:"Control",code:"ControlLeft",keyCode:17,which:17,ctrlKey:false}));});
  }
  async function keyStroke(key,options={}) {
    const special={ArrowDown:["ArrowDown",40],Escape:["Escape",27]};
    const [code,keyCode]=special[key]||[`Key${key.toUpperCase()}`,key.toUpperCase().charCodeAt(0)];
    const target=document.activeElement||document.querySelector("canvas");
    const props={key,code,keyCode,which:keyCode,bubbles:true,cancelable:true,...options};
    target?.dispatchEvent(new KeyboardEvent("keydown",props));
    await new Promise(resolve=>requestAnimationFrame(resolve));
    target?.dispatchEvent(new KeyboardEvent("keyup",{...props,altKey:false,ctrlKey:false,shiftKey:false}));
    await new Promise(resolve=>requestAnimationFrame(resolve));
  }
  async function presentationSaveAs() {
    // DeckCraft's Save shortcut defaults to .deckcraft. Its File sidebar exposes a
    // keyboard-accessible Save As page whose initial format is actual PPTX.
    document.querySelector("canvas")?.focus();
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    await keyStroke("f",{altKey:true});
    for(let i=0;i<5;i++)await keyStroke("ArrowDown");
  }
  window.addEventListener("message",async event=>{
    if(event.source!==parent||event.origin!==origin||!event.data)return;
    const message=event.data;
    if(message.type==="folio:visibility")setActive(message.active===true);
    else if(message.type==="folio:save-result"){
      const job=pending.get(message.requestId);pending.delete(message.requestId);
      if(message.ok)job?.resolve();else job?.reject(new DOMException(message.error||"Exportación cancelada.","AbortError"));
    } else if(message.type==="folio:import") {
      try {
        const url=new URL(message.url,location.href);
        if(url.origin!==origin&&!url.href.startsWith(`blob:${origin}/`))throw new Error("Ubicación del documento bloqueada.");
        const response=await fetch(url);if(!response.ok)throw new Error(`No se pudo leer el documento (${response.status}).`);
        const blob=await response.blob();if(blob.size>100*1024*1024)throw new Error("Este documento supera el límite de 100 MB.");
        const file=new File([blob],String(message.name||"Documento"),{type:blob.type});
        const data=new DataTransfer();data.items.add(file);
        const canvas=document.querySelector("canvas");if(!canvas)throw new Error("El editor todavía no está listo.");
        // A document finishing its import in the other visible side must not steal input.
        if(active && window.frameElement?.dataset.focused!=="false")canvas.focus();
        for(const type of ["dragenter","dragover","drop"]) canvas.dispatchEvent(new DragEvent(type,{bubbles:true,cancelable:true,dataTransfer:data,clientX:Math.max(20,canvas.clientWidth/2),clientY:Math.max(150,canvas.clientHeight/2)}));
      } catch(error) {send({type:"folio:error",message:String(error.message||error)});}
    } else if(message.type==="folio:readonly" && location.pathname.includes("/wordcraft/")) {
      window.__folioReadOnly=message.readOnly===true;
      window.dispatchEvent(new Event("resize"));
      document.querySelector("canvas")?.dispatchEvent(new MouseEvent("mouseleave"));
    } else if(message.type==="folio:appearance") {
      window.__folioDark=message.dark===true;
      window.dispatchEvent(new Event("resize"));
      // Eframe sleeps when its canvas is idle. A pointer leaving the canvas
      // schedules a native repaint without changing document data or focus.
      const canvas=document.querySelector("canvas");
      canvas?.dispatchEvent(new MouseEvent("mouseleave"));
    } else if(message.type==="folio:command") {
      if(window.__folioReadOnly && ["undo","redo","paste"].includes(message.command))return;
      if(message.command==="save") {
        if(location.pathname.includes("/deckcraft/"))presentationSaveAs();else shortcut("s");
      }
      else if(message.command==="undo")shortcut("z");
      else if(message.command==="redo")shortcut("y");
      else if(message.command==="back"){
        document.querySelector("canvas")?.focus();
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        await keyStroke("Escape");
      }
      else if(message.command==="focus"){
        const target=document.querySelector("textarea,input")||document.querySelector("canvas");target?.focus();
      } else if(message.command==="paste"){
        document.querySelector("canvas")?.focus();
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        const target=document.activeElement||document.querySelector("canvas");
        const data=new DataTransfer();data.setData("text/plain",message.text||"");
        target?.dispatchEvent(new ClipboardEvent("paste",{bubbles:true,cancelable:true,clipboardData:data}));
      }
    } else if(message.type==="folio:clipboard-result"){
      const job=pending.get(message.requestId);pending.delete(message.requestId);job?.resolve(String(message.text||""));
    }
  });
  // WebViews expose Clipboard inconsistently. Keep toolbar copy/paste connected to Android.
  try {
    Object.defineProperty(navigator,"clipboard",{configurable:true,value:{
      async writeText(text){send({type:"folio:clipboard-write",text:String(text)});},
      readText(){const requestId=crypto.randomUUID();return new Promise((resolve,reject)=>{pending.set(requestId,{resolve,reject});send({type:"folio:clipboard-read",requestId});});}
    }});
  } catch (_) {}
  function watchReady() {
    const id=document.querySelector("canvas")?.id;
    if(!id){send({type:"folio:failed",message:"No se encontró el área de edición."});return;}
    const loading=document.getElementById(`${id.replace(/_canvas$/,"")}_loading`);
    if(loading){
      const timer=setInterval(()=>{
        if(!loading.isConnected){clearInterval(timer);requestAnimationFrame(()=>send({type:"folio:ready"}));}
        else if(/failed to start/i.test(loading.textContent||"")){clearInterval(timer);send({type:"folio:failed",message:loading.textContent});}
      },100);
    } else requestAnimationFrame(()=>requestAnimationFrame(()=>send({type:"folio:ready"})));
  }
  window.addEventListener("TrunkApplicationStarted",watchReady,{once:true});
  window.addEventListener("unhandledrejection",event=>send({type:"folio:error",message:String(event.reason?.message||event.reason)}));
})();
