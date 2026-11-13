// The service worker with fake caches (a test page on localhost never registers it):
// • on update, the pictures of the version before are kept (a page of that version may still be open, offline), older ones go;
// • an answer that is not a success (404, 500) is replaced by the kept copy.
// usage: node tests/sw_check.js www/sw.js
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync(process.argv[2] || 'www/sw.js', 'utf8');
const SCOPE = 'https://x.test/app/', abs = f => new URL(f, SCOPE).href;
class Res { constructor(body, status = 200) { this.body = body; this.status = status; this.ok = status >= 200 && status < 300; } clone() { return this; } async json() { return JSON.parse(this.body); } }
class Cache {
  constructor() { this.m = new Map(); }
  key(r) { return typeof r === 'string' ? abs(r) : r.url; }
  async match(r) { return this.m.get(this.key(r)); }
  async put(r, x) { this.m.set(this.key(r), x); }
  async keys() { return [...this.m.keys()].map(url => ({ url })); }
  async delete(r) { return this.m.delete(this.key(r)); }
  async addAll(list) { for (const f of list) this.m.set(abs(f), new Res('shell')); }
}
const stores = new Map();
const caches = {
  async open(n) { if (!stores.has(n)) stores.set(n, new Cache()); return stores.get(n); },
  async keys() { return [...stores.keys()]; },
  async delete(n) { return stores.delete(n); },
  async match(r) { for (const c of stores.values()) { const x = await c.match(r); if (x) return x; } },
};
let answer = () => new Res('net', 200);
function load() {
  const on = {};
  const self = { addEventListener: (t, f) => on[t] = f, registration: { scope: SCOPE }, skipWaiting() {}, clients: { claim: async () => {} } };
  const ctx = { self, caches, fetch: async () => answer(), URL, location: { origin: 'https://x.test' }, setTimeout, clearTimeout, Promise, JSON, Set, Map,
    Response: class extends Res { constructor(b, init) { super(b, (init && init.status) || 200); } } };
  vm.createContext(ctx); vm.runInContext(src, ctx);
  ctx.PICS_ = vm.runInContext('PICS', ctx); ctx.C_ = vm.runInContext('C', ctx); ctx.IMG_ = vm.runInContext('IMG', ctx);
  return { on, PICS: ctx.PICS_, C: ctx.C_, IMG: ctx.IMG_ };
}
const fails = [];
const check = (ok, msg) => { console.log((ok ? '✓ ' : '✗ ') + msg); if (!ok) fails.push(msg); };
(async () => {
  const sw = load();
  const img = await caches.open(sw.IMG), LIST = abs('__pics__');
  // the version before kept its own list: old-a was one of its pictures; older-o belonged to the one before it
  await img.put(abs('img/old-a.jpg'), new Res('a')); await img.put(abs('img/older-o.jpg'), new Res('o'));
  await img.put(LIST, new Res(JSON.stringify(['img/old-a.jpg'])));
  await img.put(abs(sw.PICS[0]), new Res('p'));
  let ev = { waitUntil(p) { this.p = p; } }; sw.on.activate(ev); await ev.p;
  const has = async f => !!(await img.match(abs(f)));
  check(await has('img/old-a.jpg') && !(await has('img/older-o.jpg')) && await has(sw.PICS[0]), 'an update keeps the pictures of the version before, and drops older ones');
  check(JSON.stringify(await (await img.match(LIST)).json()) === JSON.stringify(sw.PICS), '…and remembers its own pictures for the next update');
  ev = { waitUntil(p) { this.p = p; } }; sw.on.activate(ev); await ev.p;
  check(!(await has('img/old-a.jpg')) && await has(sw.PICS[0]), 'the next update lets them go');
  // a server answering 500 while it is being updated: the kept copy is shown, not the error
  const c = await caches.open(sw.C); await c.put(abs('index.html'), new Res('kept'));
  answer = () => new Res('error', 500);
  let fe = { request: { method: 'GET', url: abs('index.html'), mode: 'navigate' }, respondWith(p) { this.p = p; } }; sw.on.fetch(fe);
  check((await fe.p).body === 'kept', 'a 500 from the server: the kept copy of the page');
  answer = () => new Res('fresh', 200);
  fe = { request: { method: 'GET', url: abs('index.html'), mode: 'navigate' }, respondWith(p) { this.p = p; } }; sw.on.fetch(fe);
  check((await fe.p).body === 'fresh', 'a good answer is used, and kept');
  answer = () => new Res('missing', 404);
  fe = { request: { method: 'GET', url: abs('nothing-kept.js'), mode: 'no-cors' }, respondWith(p) { this.p = p; } }; sw.on.fetch(fe);
  check((await fe.p).status === 404, 'with no kept copy, the error itself is returned');
  console.log(`\n${fails.length} failures`); process.exit(fails.length ? 1 : 0);
})();
