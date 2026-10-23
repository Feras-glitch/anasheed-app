#!/usr/bin/env python3
"""Build أنشودتي.

Outputs:
  www/index.html            PWA / Android / Windows build (fonts embedded when available)
  www/manifest.webmanifest, www/sw.js, www/icons/*
  dist/أنشودتي.html          single self-contained file (no PWA tags)

Fonts: if fonts/node_modules/@fontsource/{amiri,cairo} exist (CI installs them),
they are embedded as base64; otherwise the page links Google Fonts.
"""
import base64, datetime, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)
sys.path.insert(0, P('content'))

# ---------- poems ----------
src = open(P('content', 'texts.md'), encoding='utf-8').read()
poems = []
for s in re.split(r'\n### ', src)[1:]:
    head, _, body = s.partition('\n')
    m = re.match(r'(\S+)\.\s*(.+?)(?:\s+—\s+(.+))?$', head.strip())
    if not m:
        continue
    num, title, poet = m.groups()
    poet = re.sub(r'\s*\(.*$', '', poet or 'حكمة عربية').strip()
    body = body.split('\n---')[0]
    lines = [l.strip() for l in body.split('\n') if ' / ' in l and not l.startswith('(')]
    if not lines:
        continue
    age = re.search(r'(\d+)[–-](\d+)\s*سن', body)
    meta = body.strip().split('\n')[0]
    p = {'id': num, 'title': re.sub(r'\s*\(.*?\)\s*', ' ', title).strip(), 'poet': poet,
         'age': [int(age.group(1)), int(age.group(2))] if age else [6, 12],
         'verses': [l.split(' / ', 1) for l in lines]}
    if 'مع الوالد' in meta:
        p['note'] = '👨‍👧 يُستحسن أن تقرأها مع والدك: قصتها حزينة.'
    poems.append(p)

import glossary
G = dict(glossary.G)
OVR = getattr(glossary, 'OVR', {})
IMG_OFF = getattr(glossary, 'IMG_OFF', [])

def key(w):
    w = re.sub('[ً-ْٰـ]', '', w)
    return re.sub('[^؀-ۿ]', '', w)

toks = {key(w) for p in poems for v in p['verses'] for h in v for w in h.split()}
missing = [k for k in G if k not in toks]
bad = [(p['id'], i + 1) for p in poems for i, v in enumerate(p['verses']) if len(v) != 2 or not all(x.strip() for x in v)]
# overrides: "poem|word" or "poem:verse|word" must point to a real word in that poem/verse
def ovr_ok(k):
    loc, _, w = k.partition('|')
    pid, _, vn = loc.partition(':')
    p = next((x for x in poems if x['id'] == pid), None)
    if not p:
        return False
    vs = [p['verses'][int(vn) - 1]] if vn else p['verses']
    return any(key(t) == w for v in vs for h in v for t in h.split())
missing += [k for k in list(OVR) + list(IMG_OFF) if not ovr_ok(k)]
print(f'{len(poems)} poems · glossary {len(G)} · missing keys {missing} · malformed verses {bad}', file=sys.stderr)
if missing or bad:
    sys.exit('build failed: fix the problems above')

images_d = json.load(open(P('content', 'images.json'), encoding='utf-8'))
for k in IMG_OFF:
    images_d[k] = None
images = json.dumps(images_d, ensure_ascii=False)
G.update(OVR)
story = open(P('content', 'story.json'), encoding='utf-8').read()
story_d = json.loads(story)
for pid, sc in story_d.items():
    p = next((x for x in poems if x['id'] == pid), None)
    assert p and all(0 <= s['v'] < len(p['verses']) for s in sc), f'story {pid} points to a missing verse'

# ---------- fonts ----------
FS = P('fonts', 'node_modules', '@fontsource')
def font_css():
    if not os.path.isdir(os.path.join(FS, 'amiri')):
        print('fonts: not found → Google Fonts link', file=sys.stderr)
        return ('<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?'
                'family=Amiri:wght@400;700&family=Cairo:wght@400;700&display=swap" rel="stylesheet">')
    out = []
    for fam in ('amiri', 'cairo'):
        for sub in ('arabic', 'latin'):
            for wt in ('400', '700'):
                css = os.path.join(FS, fam, f'{sub}-{wt}.css')
                if not os.path.exists(css):
                    continue
                c = open(css, encoding='utf-8').read()
                def inline(m):
                    f = os.path.normpath(os.path.join(FS, fam, m.group(1)))
                    if not f.endswith('.woff2'):
                        return ''
                    return 'url(data:font/woff2;base64,' + base64.b64encode(open(f, 'rb').read()).decode() + ") format('woff2')"
                c = re.sub(r"url\((\./files/[^)]+?\.woff2)\)\s*format\('woff2'\)", inline, c)
                c = re.sub(r",\s*url\(\./files/[^)]+?\.woff\)\s*format\('woff'\)", '', c)
                out.append(c)
    print(f'fonts: embedded {len(out)} faces', file=sys.stderr)
    return '<style>' + '\n'.join(out) + '</style>'

version = os.environ.get('APP_VERSION') or datetime.date.today().isoformat()
tpl = open(P('src', 'template.html'), encoding='utf-8').read()
page = (tpl.replace('/*__VERSION__*/', version)
           .replace('/*__POEMS__*/', json.dumps(poems, ensure_ascii=False))
           .replace('/*__MEANINGS__*/', json.dumps(G, ensure_ascii=False))
           .replace('/*__IMAGES__*/', images)
           .replace('/*__STORY__*/', story)
           .replace('<!--__FONTS__-->', font_css()))
assert '/*__' not in page, 'unfilled placeholder'

# ---------- www (PWA / native shells) ----------
www = P('www')
shutil.rmtree(www, ignore_errors=True)
os.makedirs(os.path.join(www, 'icons'))
for f in ('icon-192.png', 'icon-512.png', 'maskable-512.png', 'apple-touch-icon.png'):
    shutil.copy(P('icons', f), os.path.join(www, 'icons', f))
pwa = ('<link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icons/apple-touch-icon.png">'
       '<link rel="icon" href="icons/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes">'
       '<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="أنشودتي">')
open(os.path.join(www, 'index.html'), 'w', encoding='utf-8').write(page.replace('<!--__PWA__-->', pwa))
json.dump({
    'name': 'أنشودتي', 'short_name': 'أنشودتي', 'description': 'مكتبة أناشيد للأطفال بصوتهم',
    'lang': 'ar', 'dir': 'rtl', 'start_url': './', 'scope': './', 'display': 'standalone',
    'background_color': '#fbf6ec', 'theme_color': '#F1E4C9', 'orientation': 'any',
    'icons': [{'src': 'icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
              {'src': 'icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
              {'src': 'icons/maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}]
}, open(os.path.join(www, 'manifest.webmanifest'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(www, 'sw.js'), 'w', encoding='utf-8').write(f"""const C='anasheed-{version}';
const FILES=['./','index.html','manifest.webmanifest','icons/icon-192.png','icons/icon-512.png'];
self.addEventListener('install',e=>{{e.waitUntil(caches.open(C).then(c=>c.addAll(FILES)));self.skipWaiting()}});
self.addEventListener('activate',e=>{{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))}});
// network first, but never wait more than 3 s for a slow connection
self.addEventListener('fetch',e=>{{if(e.request.method!=='GET')return;
  const cached=()=>caches.match(e.request,{{ignoreSearch:true}}).then(r=>r||caches.match('index.html'));
  const net=fetch(e.request).then(r=>{{if(r.ok){{const x=r.clone();caches.open(C).then(c=>c.put(e.request,x))}}return r}});
  e.respondWith(Promise.race([net,new Promise((_,rej)=>setTimeout(rej,3000))]).catch(()=>cached().then(r=>r||net)))}});
""")

# ---------- dist: single file ----------
os.makedirs(P('dist'), exist_ok=True)
open(P('dist', 'أنشودتي.html'), 'w', encoding='utf-8').write(page.replace('<!--__PWA__-->', ''))
print(f'built version {version}: www/index.html {os.path.getsize(os.path.join(www, "index.html"))//1024} KB', file=sys.stderr)
