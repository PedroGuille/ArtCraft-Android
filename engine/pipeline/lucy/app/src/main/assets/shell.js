/* Lucy's Android host for the four patched document engines. */
"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const native = window.AndroidFolio;
  for (const button of document.querySelectorAll("[data-close]")) {
    button.ariaLabel = "Cerrar";
    button.onclick = () => $(button.dataset.close).close();
  }
  for (const dialog of document.querySelectorAll("dialog")) dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  const engines = {
    wordcraft:{label:"Documentos",name:"Documento.docx",exts:["docx","docm","dotx","dotm","doc","dot","odt","rtf","txt","md","html","htm","tex"],template:"blank.docx"},
    gridcraft:{label:"Hojas de cálculo",name:"Libro.xlsx",exts:["xlsx","xlsm","xltx","xls","csv","tsv","ods","xlsb"],template:"blank.xlsx"},
    deckcraft:{label:"Presentaciones",name:"Presentación.pptx",exts:["pptx","potx","ppsx","deckcraft"]},
    pdfcraft:{label:"PDF",name:"Documento.pdf",exts:["pdf"],template:"blank.pdf"}
  };
  let current = null, recoveries = [], toastTimer, exportChain = Promise.resolve();
  const sessions = [], newCounts = {}, panes = [null,null];
  let splitView = false, focusedPane = 0, atHome = true;
  const nativeSaves = new Map();
  const post = message => native?.post(JSON.stringify(message));
  let darkPages = true;
  try { const saved=localStorage.getItem("lucy:dark-pages-v2"); if(saved!==null) darkPages=saved==="true"; } catch (_) {}
  function setAppearance(dark) {
    darkPages=!!dark;
    document.body.classList.toggle("dark",darkPages);
    document.documentElement.style.colorScheme=darkPages?"dark":"light";
    document.querySelector('meta[name="theme-color"]').content=darkPages?"#252925":"#f7f8fa";
    $("editor-dark").setAttribute("aria-checked",String(darkPages));
    $("editor-dark").textContent=`${darkPages?"☑":"☐"} ${"Modo oscuro"}`;
    for(const session of sessions) {
      session.frame.dataset.dark=String(darkPages);
      sendTo(session,{type:"folio:appearance",dark:darkPages});
    }
    try { localStorage.setItem("lucy:dark-pages-v2",String(darkPages)); } catch (_) {}
    post({type:"appearance",dark:darkPages});
  }
  setAppearance(darkPages);
  $("editor-dark").onclick=()=>setAppearance(!darkPages);
  const engineFor = name => {
    const ext = String(name).split(".").pop().toLowerCase();
    return Object.keys(engines).find(key => engines[key].exts.includes(ext));
  };
  const size = value => value >= 1048576 ? `${(value / 1048576).toFixed(1)} MB` : `${Math.max(1,Math.round(value/1024))} KB`;
  function toast(message) { $("toast").textContent = message; $("toast").classList.remove("hidden"); clearTimeout(toastTimer); toastTimer = setTimeout(() => $("toast").classList.add("hidden"), 6500); }
  function renderRecoveries() {
    const list = $("recovery-list"); list.replaceChildren();
    if (!recoveries.length) {
      const empty = document.createElement("p"); empty.textContent = "No hay copias guardadas."; list.append(empty);
    }
    for (const item of recoveries) {
      const row = document.createElement("div"); row.className = "recovery-row";
      const open = document.createElement("button"); open.className = "recovery-open";
      const name = document.createElement("strong"); name.textContent = String(item.name);
      const detail = document.createElement("small"); detail.textContent = `${size(item.size)} · ${new Date(item.time).toLocaleDateString("es-UY")}`;
      open.append(name, detail); open.onclick = () => { $("recoveries-dialog").close(); post({type:"openRecovery",id:item.id}); };
      const share = document.createElement("button"); share.className = "file-action"; share.textContent = "Compartir"; share.onclick = () => post({type:"share",id:item.id});
      const remove = document.createElement("button"); remove.className = "file-action"; remove.textContent = "×"; remove.ariaLabel = "Eliminar copia guardada"; remove.onclick = () => post({type:"deleteRecovery",id:item.id});
      row.append(open, share, remove); list.append(row);
    }
  }
  function confirmAction(title, body, label) {
    return new Promise(resolve => {
      const dialog = $("confirm");
      if (dialog.open) return resolve(false);
      $("confirm-title").textContent = title;
      $("confirm-body").textContent = body;
      $("close-editor").textContent = label;
      $("keep-editing").onclick = () => { dialog.close(); resolve(false); };
      $("close-editor").onclick = () => { dialog.close(); resolve(true); };
      dialog.oncancel = event => { event.preventDefault(); dialog.close(); resolve(false); };
      dialog.showModal();
    });
  }
  function sendTo(session, message) {
    if (session?.frame.contentWindow) session.frame.contentWindow.postMessage(message,location.origin);
  }
  function renderTabs() {
    document.body.classList.toggle("has-documents",sessions.length > 0);
    $("document-bar").classList.toggle("hidden",!sessions.length);
    $("tabs-home").setAttribute("aria-pressed",String(atHome));
    $("tabs-split").textContent = splitView ? "Desdividir" : "Dividir";
    $("tabs-split").setAttribute("aria-pressed",String(splitView));
    $("tabs-split").disabled = !sessions.length;
    $("tabs-split").title = splitView ? "Volver a un documento. Toca un lado y después una pestaña para cambiar su documento." : "Ver dos documentos lado a lado";
    $("document-tabs").setAttribute("aria-multiselectable",String(splitView));
    for (const session of sessions) {
      const visible = isVisible(session), pane = panes.indexOf(session);
      session.tab.classList.toggle("is-active",session === current);
      session.tab.classList.toggle("is-visible",visible);
      session.tabBadge.textContent = visible && splitView ? String(pane+1) : "";
      session.tabBadge.classList.toggle("hidden",!visible || !splitView);
      session.tab.classList.toggle("is-busy",session.exports > 0);
      session.tab.querySelector(".document-tab-name").textContent = session.title;
      session.tabButton.setAttribute("aria-selected",String(visible));
      session.tabButton.setAttribute("aria-label",`${session.title} · ${engines[session.id].label}${visible && splitView ? " · "+(pane === 0 ? "Panel izquierdo" : "Panel derecho") : ""}`);
      session.tabButton.tabIndex = session === current || (!current && session === sessions[0]) ? 0 : -1;
      session.tabButton.title = session.title;
      session.closeButton.setAttribute("aria-label",`Cerrar ${session.title}`);
      if (session.tab.parentNode !== $("document-tabs")) $("document-tabs").append(session.tab);
    }
  }
  function renderEditor() {
    for (const button of document.querySelectorAll("[data-editor-action]")) button.disabled = !current?.ready;
    document.querySelector(".menu-document").classList.toggle("hidden",!current);
    $("editor-loading").classList.toggle("hidden",atHome || !current || current.ready);
    const reading = $("editor-readonly");
    reading.classList.toggle("hidden",current?.id!=="wordcraft");
    reading.disabled = !current?.ready;
    reading.setAttribute("aria-checked",String(!!current?.readOnly));
    reading.textContent = `${current?.readOnly?"☑":"☐"} Solo lectura`;
    if(current?.readOnly) for(const id of ["editor-undo","editor-redo","editor-paste","editor-keyboard"]) $(id).disabled=true;
    if (!current) return;
    $("editor-name").textContent = current.title;
    $("editor-type").textContent = engines[current.id].label;
    $("loading-label").textContent = current.error || (current.slow ? "Iniciando… Usa una versión reciente de Android System WebView." : `Abriendo ${engines[current.id].label.toLowerCase()}…`);
    $("editor-fit").textContent = `${"Escala de interfaz"} · ${Math.round(current.scale*100)}%`;
  }
  function setMenu(open) {
    if (open) renderEditor();
    $("new-menu").classList.toggle("hidden",!open);
    $("tabs-add").setAttribute("aria-expanded",String(open));
  }
  function isVisible(session) {
    return !atHome && (session === panes[0] || (splitView && session === panes[1]));
  }
  function renderView() {
    $("editor").classList.toggle("hidden",atHome);
    $("workspace").classList.toggle("hidden",!atHome);
    document.body.classList.toggle("editor-open",!atHome);
    document.body.classList.toggle("split-view",splitView && !atHome);
    $("editor").style.setProperty("--focused-pane-left",`${splitView ? focusedPane*50 : 0}%`);
    $("editor").style.setProperty("--focused-pane-width",splitView ? "50%" : "100%");
    for (const session of sessions) {
      const visible = isVisible(session);
      session.frame.dataset.active = String(visible);
      session.frame.dataset.focused = String(session === current);
      session.frame.classList.toggle("active-frame",visible);
      session.frame.inert = !visible;
      session.frame.setAttribute("aria-hidden",String(!visible));
      applyScale(session);
      sendTo(session,{type:"folio:visibility",active:visible});
    }
    for (let i=0;i<2;i++) $(`empty-pane-${i}`).classList.toggle("hidden",atHome || !splitView || !!panes[i]);
    $("split-divider").classList.toggle("hidden",!splitView || atHome);
    $("pane-focus").classList.toggle("hidden",!splitView || atHome);
    renderTabs(); renderEditor();
  }
  function focusPane(index) {
    if (atHome || index < 0 || index > (splitView ? 1 : 0)) return;
    if (focusedPane === index && current === panes[index]) return;
    focusedPane = index;
    current = panes[index];
    setMenu(false); renderView();
  }
  function activate(session) {
    if (session && !sessions.includes(session)) return;
    setMenu(false);
    atHome = !session;
    if (session) {
      const visiblePane = panes.indexOf(session);
      if (splitView && visiblePane >= 0) focusedPane = visiblePane;
      else { if (!splitView) focusedPane = 0; panes[focusedPane] = session; }
    }
    current = session;
    renderView();
    if (session) {
      session.tab.scrollIntoView({block:"nearest",inline:"nearest"});
      if (session.ready) session.frame.contentWindow.focus();
    }
  }
  function toggleSplit() {
    if (!sessions.length) return;
    setMenu(false);
    const primary = current || panes[focusedPane] || panes[1-focusedPane] || sessions[0];
    if (splitView) {
      splitView = false; panes[0] = primary; panes[1] = null; focusedPane = 0;
    } else {
      splitView = true; panes[0] = primary; panes[1] = sessions.find(session=>session !== primary) || null;
      focusedPane = panes[1] ? 0 : 1;
    }
    atHome = false; current = panes[focusedPane]; renderView();
    if (current?.ready) current.frame.contentWindow.focus();
  }
  async function closeSession(session) {
    if (!sessions.includes(session)) return;
    if (session.exports) { toast("Finaliza la exportación de este documento primero."); return; }
    const accepted = await confirmAction(`¿Cerrar «${session.title}»?`,"Guarda una copia primero. Se descartarán los cambios de esta pestaña posteriores a la última exportación.","Cerrar pestaña");
    if (!accepted || !sessions.includes(session)) return;
    // An editor may start exporting while its close dialog is open.
    if (session.exports) { toast("Finaliza la exportación de este documento primero."); return; }
    const index = sessions.indexOf(session), wasActive = current === session;
    clearTimeout(session.timer);
    if (session.file?.browserUrl) URL.revokeObjectURL(session.file.browserUrl);
    if (session.file?.url) post({type:"releaseDocument",url:session.file.url});
    session.frame.remove(); session.tab.remove(); sessions.splice(index,1);
    const pane = panes.indexOf(session);
    if (pane >= 0) panes[pane] = sessions.find(item=>!panes.includes(item)) || null;
    if (!sessions.length) { splitView = false; focusedPane = 0; panes[0] = panes[1] = null; atHome = true; }
    else if (wasActive && !panes[focusedPane] && splitView && panes[1-focusedPane]) focusedPane = 1-focusedPane;
    current = atHome ? null : panes[focusedPane];
    renderView();
    if (wasActive && current?.ready) current.frame.contentWindow.focus();
  }
  function applyScale(session = current) {
    if (!session) return;
    const pane = panes.indexOf(session), half = splitView && pane >= 0;
    session.frame.style.left = `${half ? pane*50 : 0}%`;
    session.frame.style.width = `${(half ? 50 : 100)/session.scale}%`;
    session.frame.style.height = `${100/session.scale}%`;
    session.frame.style.transform = `scale(${session.scale})`;
    if (session === current) $("editor-fit").textContent = `${"Escala de interfaz"} · ${Math.round(session.scale*100)}%`;
  }
  function launch(id, file, isNew = false) {
    if (!(id in engines)) {
      toast("Este formato no es compatible.");
      if (file?.browserUrl) URL.revokeObjectURL(file.browserUrl);
      if (file?.url) post({type:"releaseDocument",url:file.url});
      return;
    }
    const existing = file && sessions.find(item => (file.uri && item.file?.uri === file.uri) || (file.recoveryId && item.file?.recoveryId === file.recoveryId));
    if (existing) {
      if (file.url !== existing.file.url) post({type:"releaseDocument",url:file.url});
      activate(existing); return;
    }
    const engine = engines[id];
    const frame = document.createElement("iframe"); frame.title = engine.label;
    frame.setAttribute("allow","clipboard-read; clipboard-write; fullscreen");
    newCounts[id] = (newCounts[id] || 0) + (isNew ? 1 : 0);
    const title = file?.name || engine.name.replace(/(\.[^.]+)$/,`${newCounts[id] > 1 ? " " + newCounts[id] : ""}$1`);
    const sessionId = crypto.randomUUID();
    const session = {id,frame,file,isNew,title,scale:innerWidth < 700 ? .85 : 1,ready:false,readOnly:false,exports:0};
    frame.id = `frame-${sessionId}`;
    const item = document.createElement("div"); item.className = "document-tab"; item.dataset.engine = id;
    const button = document.createElement("button"); button.className = "document-tab-button"; button.id = `tab-${sessionId}`; button.setAttribute("role","tab"); button.setAttribute("aria-controls",frame.id);
    button.innerHTML = `<span class="tab-icon ${id}" aria-hidden="true">${{wordcraft:"W",gridcraft:"X",deckcraft:"P",pdfcraft:"PDF"}[id]}</span><span class="document-tab-name"></span>`;
    button.onclick = () => activate(session);
    button.onkeydown = event => {
      const index = sessions.indexOf(session);
      const next = event.key === "ArrowRight" ? sessions[(index+1)%sessions.length] : event.key === "ArrowLeft" ? sessions[(index-1+sessions.length)%sessions.length] : event.key === "Home" ? sessions[0] : event.key === "End" ? sessions[sessions.length-1] : null;
      if (next) { event.preventDefault(); activate(next); next.tabButton.focus(); }
    };
    const close = document.createElement("button"); close.className = "document-tab-close"; close.textContent = "×"; close.onclick = () => closeSession(session);
    const badge = document.createElement("span"); badge.className = "document-tab-pane hidden"; badge.setAttribute("aria-hidden","true"); button.append(badge); session.tabBadge = badge;
    item.append(button,close); session.tab = item; session.tabButton = button; session.closeButton = close;
    frame.setAttribute("aria-labelledby",button.id);
    sessions.push(session);
    // Set data-active before navigation so the adapter can start a late-loading
    // background tab paused. Every document retains its own live iframe.
    frame.dataset.active = "true";
    frame.dataset.dark = String(darkPages);
    frame.dataset.readOnly = "false";
    frame.src = `engines/${id}/index.html?webgl&blank`;
    $("editor-stage").append(frame); applyScale(session); activate(session);
    session.timer = setTimeout(() => { if (!session.ready) { session.slow = true; if (current === session) renderEditor(); } },45000);
  }
  function toEditor(message) { if (current?.ready) sendTo(current,message); }
  function openPicker() { setMenu(false); if (native) post({type:"open"}); else $("browser-open").click(); }
  $("browser-open").onchange = () => { for (const file of $("browser-open").files) { const url = URL.createObjectURL(file); launch(engineFor(file.name),{name:file.name,size:file.size,url,browserUrl:url}); } $("browser-open").value=""; };
  for (const el of document.querySelectorAll("[data-new]")) el.onclick = () => { $("create-dialog").close(); launch(el.dataset.new,null,true); };
  $("create-file").onclick = () => $("create-dialog").showModal();
  $("open-top").onclick = openPicker;
  $("editor-home").onclick = () => activate(null);
  $("loading-cancel").onclick = $("editor-home").onclick;
  $("tabs-home").onclick = $("editor-home").onclick;
  $("tabs-open").onclick = openPicker;
  $("tabs-split").onclick = toggleSplit;
  for (let i=0;i<2;i++) {
    const pane = $(`empty-pane-${i}`);
    pane.ariaLabel = i === 0 ? "Panel izquierdo" : "Panel derecho";
    pane.onpointerdown = pane.onfocusin = () => focusPane(i);
    pane.querySelector("button").onclick = () => { focusPane(i); openPicker(); };
  }
  $("tabs-open").title = "Abrir un archivo";
  $("tabs-add").onclick = () => { const open = $("new-menu").classList.contains("hidden"); setMenu(open); if (open) $("new-menu").querySelector("button:not(:disabled)")?.focus(); };
  $("tabs-home").title = $("tabs-home").ariaLabel = "Inicio";
  $("editor-home").ariaLabel = "Inicio";
  $("tabs-add").title = $("tabs-add").ariaLabel = "Menú de archivos y edición";
  $("document-tabs").ariaLabel = $("document-bar").ariaLabel = "Documentos abiertos";
  document.addEventListener("pointerdown",event => { if (!event.target.closest?.("#new-menu, #tabs-add")) setMenu(false); },true);
  document.addEventListener("keydown",event => {
    if (event.key === "Escape") { setMenu(false); $("tabs-add").focus(); }
    if (event.ctrlKey && event.key === "Tab" && sessions.length) { event.preventDefault(); stepTab(event.shiftKey ? -1 : 1); }
  });
  $("new-menu").onkeydown = event => {
    const buttons = [...$("new-menu").querySelectorAll("button")].filter(button=>!button.disabled && !button.classList.contains("hidden")), index = buttons.indexOf(document.activeElement);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); buttons[(index+(event.key === "ArrowDown" ? 1 : -1)+buttons.length)%buttons.length].focus(); }
  };
  function stepTab(direction) { if (sessions.length) activate(sessions[(sessions.indexOf(current)+direction+sessions.length)%sessions.length]); }
  $("editor-save").onclick = () => {
    setMenu(false);
    if(current?.id==="deckcraft"&&$("editor-stage").clientWidth/(splitView?2:1)/current.scale<720){
      current.restoreScale=current.scale;current.scale=$("editor-stage").clientWidth/(splitView?2:1)/720;applyScale();
    }
    toEditor({type:"folio:command",command:"save"});
  };
  function command(name,extra={}) { setMenu(false);toEditor({type:"folio:command",command:name,...extra}); }
  $("editor-readonly").onclick = () => {
    if(current?.id!=="wordcraft" || !current.ready)return;
    current.readOnly=!current.readOnly;
    current.frame.dataset.readOnly=String(current.readOnly);
    sendTo(current,{type:"folio:readonly",readOnly:current.readOnly});
    setMenu(false);renderEditor();
  };
  $("editor-undo").onclick = () => command("undo");
  $("editor-redo").onclick = () => command("redo");
  $("editor-back").onclick = () => command("back");
  $("editor-paste").onclick = () => command("paste",{text:native?.readClipboard() || ""});
  $("editor-keyboard").onclick = () => { command("focus");post({type:"keyboard"}); };
  $("editor-fit").onclick = () => { setMenu(false);if (current) { current.scale = current.scale === 1 ? .85 : current.scale === .85 ? .7 : current.scale === .7 ? .5 : 1;applyScale(); } };
  $("licenses-close").onclick = () => $("licenses-dialog").close();
  $("show-recoveries").onclick = () => { setMenu(false); renderRecoveries(); $("recoveries-dialog").showModal(); post({type:"recoveries"}); };
  $("show-licenses").onclick = async () => { setMenu(false); try { $("license-content").textContent = await (await fetch("THIRD_PARTY_NOTICES.txt")).text(); $("licenses-dialog").showModal(); } catch (_) { toast("No se pudieron cargar las licencias."); } };

  function base64(buffer) { const bytes = new Uint8Array(buffer); let binary=""; for (let i=0;i<bytes.length;i+=8192) binary+=String.fromCharCode(...bytes.subarray(i,i+8192)); return btoa(binary); }
  async function saveBlob(name,blob) {
    if (!(blob instanceof Blob) || !blob.size || blob.size > 100*1024*1024) throw new Error("Las exportaciones deben tener entre 1 byte y 100 MB.");
    if (!native) {
      const url=URL.createObjectURL(blob),a=document.createElement("a");a.download=name;a.href=url;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);return;
    }
    const response=JSON.parse(native.beginSave(JSON.stringify({name,size:blob.size})));
    if (!response.id) throw new Error(response.error||"No se pudo iniciar la exportación.");
    const id=response.id;
    const result=new Promise((resolve,reject)=>nativeSaves.set(id,{resolve,reject}));
    // Register before finishing: an immediate provider failure can report synchronously.
    try {
      for (let offset=0;offset<blob.size;offset+=65536) {
        const chunk=base64(await blob.slice(offset,offset+65536).arrayBuffer());
        if (!native.appendSave(id,chunk)) throw new Error("No se pudo escribir la copia guardada.");
      }
      if (!native.finishSave(id)) throw new Error("La exportación está incompleta.");
    } catch (error) { native.abortSave(id);nativeSaves.delete(id);throw error; }
    return result;
  }
  window.addEventListener("message",event=>{
    if (event.origin!==location.origin || !event.data || typeof event.data.type!=="string") return;
    const owner = sessions.find(session => event.source === session.frame.contentWindow);
    if (!owner) return;
    const message=event.data;
    if (message.type==="folio:ready") {
      sendTo(owner,{type:"folio:appearance",dark:darkPages});
      if(owner.id==="wordcraft")sendTo(owner,{type:"folio:readonly",readOnly:!!owner.readOnly});
      if (owner.ready) return;
      owner.ready=true;clearTimeout(owner.timer);
      if (owner === current) renderEditor();
      const target=owner.file;
      if (target) sendTo(owner,{type:"folio:import",url:target.url,name:target.name});
      else if (owner.isNew && engines[owner.id].template) sendTo(owner,{type:"folio:import",url:`../../templates/${engines[owner.id].template}`,name:owner.title});
    } else if (message.type==="folio:interact") {
      if(isVisible(owner) && !document.querySelector("dialog[open]")) {setMenu(false);focusPane(panes.indexOf(owner));}
    } else if (message.type==="folio:focus") { if (isVisible(owner) && !document.querySelector("dialog[open]") && $("new-menu").classList.contains("hidden")) focusPane(panes.indexOf(owner)); }
    else if (message.type==="folio:failed") { clearTimeout(owner.timer);owner.error=String(message.message||"No se pudo iniciar el editor.");if(owner===current)renderEditor();toast(`${owner.title}: ${owner.error}`); }
    else if (message.type==="folio:error") toast(String(message.message||"Error del editor"));
    else if (message.type==="folio:save") {
      const sender=event.source;
      owner.exports++; renderTabs();
      const run=async()=>{
        try {
          const name=String(message.name||"Documento");
          await saveBlob(name,message.blob);
          sender.postMessage({type:"folio:save-result",requestId:message.requestId,ok:true},location.origin);
          if (engineFor(name)===owner.id) owner.title=name;
          toast("Copia guardada.");
        }
        catch (error) { sender.postMessage({type:"folio:save-result",requestId:message.requestId,ok:false,error:String(error.message||error)},location.origin);toast(String(error.message||error)); }
        finally {
          owner.exports--;
          if(owner.restoreScale){owner.scale=owner.restoreScale;delete owner.restoreScale;applyScale(owner);}
          renderTabs(); if(owner===current)renderEditor();
        }
      };
      exportChain=exportChain.then(run,run);
    } else if (message.type==="folio:clipboard-write") native?.writeClipboard(String(message.text||""));
    else if (message.type==="folio:clipboard-read") event.source.postMessage({type:"folio:clipboard-result",requestId:message.requestId,text:native?.readClipboard()||""},location.origin);
    else if (isVisible(owner) && !$("confirm").open) {
      if (owner !== current) focusPane(panes.indexOf(owner));
      if (message.type==="folio:tab-step") stepTab(message.direction === -1 ? -1 : 1);
      else if (message.type==="folio:close-tab") closeSession(owner);
      else if (message.type==="folio:open-picker") openPicker();
    }
  });
  window.FolioNative={
    onEvent(event) {
      if (event.type==="opened") launch(engineFor(event.name),event);
      else if (event.type==="recoveries") {recoveries=Array.isArray(event.items)?event.items:[];renderRecoveries();}
      else if (event.type==="saveResult") {
        const pending=nativeSaves.get(event.id);nativeSaves.delete(event.id);
        if (event.saved) pending?.resolve(); else pending?.reject(new Error(event.message||"Exportación cancelada. Hay una copia disponible en Copias guardadas."));
      } else if (event.type==="error") toast(event.message||"No se pudo completar esa acción.");
    },
    async back() {
      for (const id of ["create-dialog","recoveries-dialog","licenses-dialog"]) if ($(id).open) { $(id).close(); return; }
      if ($("confirm").open) { $("keep-editing").click(); return; }
      if (!$("new-menu").classList.contains("hidden")) { setMenu(false); return; }
      if (!atHome) { activate(null); return; }
      if (!sessions.length) { post({type:"exit"}); return; }
      if (sessions.some(session=>session.exports)) { toast("Finaliza la exportación actual primero."); return; }
      const accepted = await confirmAction("¿Cerrar todas las pestañas y salir?","Guarda copias de tus documentos primero. Se descartarán los cambios sin guardar de todas las pestañas abiertas.","Salir de Lucy");
      if (accepted && !sessions.some(session=>session.exports)) post({type:"exit"});
    }
  };
  post({type:"ready"});
})();
