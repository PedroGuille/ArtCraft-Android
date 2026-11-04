/* Focused host/iframe protocol regression checks; no browser or WASM build. */
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assets = path.resolve(__dirname, '../engine/pipeline/lucy/app/src/main/assets');
class Target {
  constructor() { this.listeners = {}; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  dispatchEvent(event) { return Promise.all((this.listeners[event.type] || []).map(fn => fn(event))); }
}
class Element extends Target {
  constructor(tag = 'div') {
    super(); this.tag = tag; this.dataset = {}; this.attributes = {}; this.children = [];
    this.style = {setProperty() {}}; this.classes = new Set(); this.open = false;
    this.classList = {
      contains: c => this.classes.has(c), add: c => this.classes.add(c), remove: c => this.classes.delete(c),
      toggle: (c, value = !this.classes.has(c)) => value ? this.classes.add(c) : this.classes.delete(c)
    };
    if (tag === 'iframe') this.contentWindow = {messages: [], postMessage(m) {this.messages.push(m);}, focus() {}};
  }
  set className(v) { this.classes = new Set(v.split(/\s+/)); }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  append(...items) { for (const item of items) {this.children.push(item); item.parentNode = this;} }
  querySelector(key) { return this.parts?.[key] || (this.parts ||= {}, this.parts[key] = new Element('button')); }
  focus() {} scrollIntoView() {} close() { this.open = false; } showModal() { this.open = true; }
}
function host(saved = {}) {
  const window = new Target(), document = new Target(), ids = new Map(), elements = [];
  for (const match of fs.readFileSync(path.join(assets, 'index.html'), 'utf8').matchAll(/<(\w+)\b([^>]*)>/g)) {
    const [, tag, attrs] = match, el = new Element(tag); elements.push(el);
    const id = attrs.match(/\bid="([^"]+)"/); if (id) {el.id = id[1]; ids.set(el.id, el);}
    el.className = attrs.match(/\bclass="([^"]+)"/)?.[1] || '';
    for (const a of attrs.matchAll(/\bdata-([\w-]+)(?:="([^"]*)")?/g)) el.dataset[a[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = a[2] || '';
  }
  document.body = elements.find(el => el.tag === 'body'); document.documentElement = new Element('html');
  document.getElementById = id => ids.get(id);
  document.querySelectorAll = q => elements.filter(el => q === 'dialog' ? el.tag === q : q === '[data-new]' ? 'new' in el.dataset : q === '[data-close]' ? 'close' in el.dataset : q === '[data-editor-action]' ? 'editorAction' in el.dataset : false);
  document.querySelector = q => q === 'dialog[open]' ? elements.find(el => el.tag === 'dialog' && el.open) : q === '.menu-document' ? elements.find(el => el.classes.has('menu-document')) : elements.find(el => el.tag === 'meta');
  document.createElement = tag => {const el = new Element(tag); elements.push(el); return el;};
  const prefs = new Map(Object.entries(saved)), nativeEvents = [];
  window.AndroidFolio = {post: raw => nativeEvents.push(JSON.parse(raw))};
  const context = {window, document, location: {origin: 'https://lucy.test'}, innerWidth: 1200, crypto: require('node:crypto').webcrypto,
    localStorage: {getItem: k => prefs.get(k) ?? null, setItem: (k,v) => prefs.set(k,v)}, setTimeout: () => 1, clearTimeout() {}, URL, Blob};
  vm.runInNewContext(fs.readFileSync(path.join(assets, 'shell.js'), 'utf8'), context);
  return {window, document, ids, prefs, nativeEvents, elements, frames: () => elements.filter(el => el.tag === 'iframe'),
    open(name) {window.FolioNative.onEvent({type: 'opened', name, url: 'https://lucy.test/file'}); return this.frames().at(-1);},
    async message(frame, type, origin = 'https://lucy.test') {await window.dispatchEvent({type: 'message', origin, source: frame.contentWindow, data: {type}});}};
}
function adapter(frame, parent, report, pathname = '/engines/wordcraft/index.html') {
  const window = new Target(), document = new Target(), canvas = new Element('canvas'), events = [];
  canvas.dispatchEvent = e => {events.push(e.type); return true;}; document.querySelector = q => q === 'canvas' ? canvas : null;
  document.activeElement = canvas; window.frameElement = frame;
  window.requestAnimationFrame = fn => {queueMicrotask(() => fn(1)); return 1;}; window.cancelAnimationFrame = () => {};
  class Anchor {click() {}}
  class Event {constructor(type, props = {}) {this.type = type; Object.assign(this, props);}}
  parent.postMessage = message => report(message);
  const context = {window, document, parent, location: {origin: 'https://lucy.test', pathname}, navigator: {}, URL: class extends URL {},
    HTMLAnchorElement: Anchor, Event, MouseEvent: Event, KeyboardEvent: Event, Blob, DOMException};
  context.requestAnimationFrame = fn => window.requestAnimationFrame(fn);
  vm.runInNewContext(fs.readFileSync(path.join(assets, 'engine-adapter.js'), 'utf8'), context);
  return {window, document, events, async message(data, source = parent, origin = 'https://lucy.test') {await window.dispatchEvent({type: 'message', source, origin, data});}};
}
(async () => {
  const h = host({'folio:dark-pages': 'false'}), $ = id => h.ids.get(id);
  assert.equal(h.nativeEvents[0].dark, true, 'legacy automatic light preference migrates to dark');
  assert.equal(host({'lucy:dark-pages-v2': 'false'}).nativeEvents[0].dark, false, 'new explicit light preference persists');
  const first = h.open('First.docx'); await h.message(first, 'folio:ready');
  $('tabs-add').onclick(); $('editor-readonly').onclick();
  assert.equal(first.dataset.readOnly, 'true'); assert.equal($('editor-paste').disabled, true);
  const second = h.open('Second.docx'); await h.message(second, 'folio:ready');
  assert.equal(second.dataset.readOnly, 'false'); assert.equal($('editor-paste').disabled, false);
  $('tabs-split').onclick();
  const pending = [], parent = {};
  const a = adapter(first, parent, message => pending.push(h.window.dispatchEvent({type: 'message', origin: 'https://lucy.test', source: first.contentWindow, data: message})));
  $('tabs-add').onclick(); assert.equal($('new-menu').classList.contains('hidden'), false);
  await a.document.dispatchEvent({type: 'pointerdown'}); await Promise.all(pending.splice(0));
  assert.equal($('new-menu').classList.contains('hidden'), true, 'touch in another visible pane dismisses menu');
  assert.equal($('editor-readonly').attributes['aria-checked'], 'true', 'pane switch retains read-only state');
  $('tabs-add').onclick(); await a.document.dispatchEvent({type: 'wheel'}); await Promise.all(pending.splice(0));
  assert.equal($('new-menu').classList.contains('hidden'), true, 'document scroll dismisses menu');
  $('tabs-add').onclick(); await h.message(first, 'folio:interact', 'https://foreign.test');
  assert.equal($('new-menu').classList.contains('hidden'), false, 'foreign origins cannot control menu');
  await h.message({contentWindow: {}}, 'folio:interact');
  assert.equal($('new-menu').classList.contains('hidden'), false, 'unknown frames cannot control menu');
  const before = a.events.length;
  for (const command of ['undo', 'redo', 'paste']) await a.message({type: 'folio:command', command});
  assert.equal(a.events.length, before, 'read-only blocks toolbar mutations');
  await a.message({type: 'folio:readonly', readOnly: false}, {});
  await a.message({type: 'folio:readonly', readOnly: false}, parent, 'https://foreign.test');
  assert.equal(a.window.__folioReadOnly, true, 'only the trusted host can change read-only');
  await a.message({type: 'folio:readonly', readOnly: false});
  await a.message({type: 'folio:command', command: 'undo'});
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(a.events.includes('keydown'), 'editing commands resume after leaving read-only');
  await a.message({type: 'folio:visibility', active: false});
  await a.document.dispatchEvent({type: 'pointerdown'}); assert.equal(pending.length, 0, 'hidden documents do not dismiss menu');
  const pdf = adapter({dataset: {}}, {}, () => {}, '/engines/pdfcraft/index.html');
  await pdf.message({type: 'folio:readonly', readOnly: true});
  assert.equal(pdf.window.__folioReadOnly, false, 'Word reading preference is not applied to PDF');
  console.log('PASS: dark defaults, per-tab reading, trusted messages, split-pane touch/scroll menu dismissal and editing resume');
})().catch(error => {console.error(error); process.exitCode = 1;});
