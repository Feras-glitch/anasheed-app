#!/usr/bin/env python3
"""Build أنشودتي.

Outputs:
  www/index.html            PWA / Android / Windows build (fonts embedded when available)
  www/manifest.webmanifest, www/sw.js, www/icons/*
  dist/أنشودتي.html          single self-contained file (no PWA tags)

Fonts: if fonts/node_modules/@fontsource/{amiri,cairo} exist (CI installs them),
they are embedded as base64; otherwise the page links Google Fonts.
"""
import base64, datetime, hashlib, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)
sys.path.insert(0, P('content'))

# ---------- poems ----------
src = open(P('content', 'texts.md'), encoding='utf-8').read()
poems = []
problems = []
FULL = {}  # poem id → all verses of the full poem (an excerpt keeps only some)
VMAP = {}  # poem id → {verse number in the full poem: verse number in the app}
for s in re.split(r'\n### ', src)[1:]:
    head, _, body = s.partition('\n')
    m = re.match(r'(\S+)\.\s*(.+?)(?:\s+—\s+(.+))?$', head.strip())
    if not m:
        # a heading that does not parse would drop its poem silently
        if any(' / ' in l for l in body.split('\n---')[0].split('\n')):
            problems.append(f'heading not understood: {head.strip()!r}')
        continue
    num, title, poet = m.groups()
    poet = re.sub(r'\s*\(.*$', '', poet or 'حكمة عربية').strip()
    body = body.split('\n---')[0]
    lines = [l.strip() for l in body.split('\n') if ' / ' in l and not l.startswith('(')]
    # a vocalized line with a "/" that is not " / " is a verse that would be dropped silently
    for l in body.split('\n'):
        if '/' in l and ' / ' not in l and 'http' not in l and len(re.findall('[ًٌٍَُِّْ]', l)) > 8:
            problems.append(f'{num}: a verse needs " / " with a space on each side: {l.strip()[:50]}')
    for l in lines:
        if l.count(' / ') != 1:
            problems.append(f'{num}: a verse needs exactly one " / ": {l[:50]}')
        if re.match(r'(المصدر|ملاحظة|http)', l) or 'http' in l:
            problems.append(f'{num}: a note line contains " / " and would become a verse: {l[:50]}')
    if not lines:
        continue
    age = re.search(r'(\d+)[–-](\d+)\s*سن', body)
    meta = body.strip().split('\n')[0]
    verses = [l.split(' / ', 1) for l in lines]
    FULL[num] = verses
    # a very long poem is memorised from an excerpt: "مقتطف للحفظ: 1-5, 11, 13-14" (numbers of the full poem)
    vmap = {i + 1: i + 1 for i in range(len(verses))}
    total = None
    ex = re.search(r'^مقتطف للحفظ:\s*(.+)$', body, re.M)
    if ex:
        keep = []
        for part in ex.group(1).replace('،', ',').split(','):
            a, _, b = part.strip().partition('-')
            keep += list(range(int(a), int(b or a) + 1))
        if not keep or keep != sorted(set(keep)) or keep[-1] > len(verses):
            problems.append(f'{num}: bad excerpt {ex.group(1)}')
        else:
            vmap = {v: i + 1 for i, v in enumerate(keep)}
            total = len(verses); verses = [verses[v - 1] for v in keep]
    p = {'id': num, 'title': re.sub(r'\s*\(.*?\)\s*', ' ', title).strip(), 'poet': poet,
         'age': [int(age.group(1)), int(age.group(2))] if age else [6, 12],
         'verses': verses}
    if total:
        p['excerpt'] = [len(verses), total]
    VMAP[num] = vmap
    foot = re.search(r'^حاشية:\s*(.+)$', body, re.M)
    if foot:
        p['foot'] = foot.group(1).strip()
    if 'مع الوالد' in meta:
        p['note'] = '👨‍👧 يُستحسن أن تقرأها مع والدك: قصتها حزينة.'
    pn = re.search(r'^ملاحظة للوالد:\s*(.+)$', body, re.M)
    if pn:
        p['note'] = '👨‍👧 ' + pn.group(1).strip()
    poems.append(p)

import glossary
G = dict(glossary.G)
# meanings for poems a parent may add by hand (e.g. «كن بلسماً»): kept, but not checked against the built-in texts
G_PARENT = getattr(glossary, 'G_PARENT', {})
# verse numbers in "poem:verse|word" keys refer to the full poem; renumber them for excerpts, drop excluded verses
def renum(k):
    loc, _, w = k.partition('|'); pid, _, vn = loc.partition(':')
    if not vn or pid not in VMAP:
        return k
    nv = VMAP[pid].get(int(vn))
    return f'{pid}:{nv}|{w}' if nv else None
OVR = {renum(k): v for k, v in getattr(glossary, 'OVR', {}).items() if renum(k)}
IMG_OFF = [renum(k) for k in getattr(glossary, 'IMG_OFF', []) if renum(k)]

def key(w):
    w = re.sub('[ً-ْٰـ]', '', w)
    return re.sub('[^؀-ۿ]', '', w)

toks = {key(w) for p in poems for v in p['verses'] for h in v for w in h.split()}
toks_full = {key(w) for vs in FULL.values() for v in vs for h in v for w in h.split()}
# a meaning for a word that is only in the part of a long poem left out of its excerpt is kept, unused
missing = [k for k in G if k not in toks and k not in toks_full]
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
def in_full(k):
    loc, _, w = k.partition('|'); pid = loc.partition(':')[0]
    return pid in FULL and any(key(x) == w for v in FULL[pid] for h in v for x in h.split())
skipped = [k for k in list(OVR) + list(IMG_OFF) if not ovr_ok(k) and in_full(k)]
OVR = {k: v for k, v in OVR.items() if k not in skipped}
IMG_OFF = [k for k in IMG_OFF if k not in skipped]
missing += [k for k in list(OVR) + list(IMG_OFF) if not ovr_ok(k)]
ids = [p['id'] for p in poems]
problems += [f'poem id used twice: {i}' for i in sorted({i for i in ids if ids.count(i) > 1})]
print(f'{len(poems)} poems · glossary {len(G)} · missing keys {missing} · malformed verses {bad}', file=sys.stderr)
for x in problems:
    print('✗', x, file=sys.stderr)
if missing or bad or problems:
    sys.exit('build failed: fix the problems above')

images_d = json.load(open(P('content', 'images.json'), encoding='utf-8'))
for k in IMG_OFF:
    images_d[k] = None
# card pictures chosen by hand (a random word's picture misled children choosing by picture)
thumbs = {k: v for k, v in json.load(open(P('content', 'thumbs.json'), encoding='utf-8')).items() if not k.startswith('_')}
for pid, src in thumbs.items():
    assert any(p['id'] == pid for p in poems), f'thumbs.json: unknown poem {pid}'
    if src in images_d:
        images_d['@thumb:' + pid] = '@' + src  # an alias: the picture is not stored twice
    else:  # a small JPEG kept in content/thumbs/
        images_d['@thumb:' + pid] = 'data:image/jpeg;base64,' + base64.b64encode(open(P(src), 'rb').read()).decode()
# character stickers: one per picture story, opened when the child memorises the whole poem
album = {k: v for k, v in json.load(open(P('content', 'album.json'), encoding='utf-8')).items() if not k.startswith('_')}
for pid, a in album.items():
    assert any(p['id'] == pid for p in poems) and a.get('name'), f'album.json: bad entry {pid}'
    images_d['@album:' + pid] = 'data:image/jpeg;base64,' + base64.b64encode(open(P(a['img']), 'rb').read()).decode()
album_names = {pid: a['name'] for pid, a in album.items()}
paths = {k: v for k, v in json.load(open(P('content', 'paths.json'), encoding='utf-8')).items() if not k.startswith('_')}
assert set(paths) == {'young', 'old'} and all(any(p['id'] == i for p in poems) for v in paths.values() for i in v), 'paths.json: unknown poem id'
G.update(OVR)
for k, v in G_PARENT.items():
    G.setdefault(k, v)
story_d = json.load(open(P('content', 'story.json'), encoding='utf-8'))
for pid, sc in story_d.items():
    p = next((x for x in poems if x['id'] == pid), None)
    assert p and sc and all(0 <= s['v'] < len(p['verses']) for s in sc), f'story {pid} is empty or points to a missing verse'
lessons = {k: v for k, v in json.load(open(P('content', 'lessons.json'), encoding='utf-8')).items() if not k.startswith('_')}
assert all(any(p['id'] == k for p in poems) for k in lessons), 'lessons.json: unknown poem id'

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
fonts = font_css()
def render(images, story):
    page = (tpl.replace('/*__VERSION__*/', version)
               .replace('/*__POEMS__*/', json.dumps(poems, ensure_ascii=False))
               .replace('/*__MEANINGS__*/', json.dumps(G, ensure_ascii=False))
               .replace('/*__IMAGES__*/', json.dumps(images, ensure_ascii=False))
               .replace('/*__STORY__*/', json.dumps(story, ensure_ascii=False))
               .replace('/*__LESSONS__*/', json.dumps(lessons, ensure_ascii=False))
               .replace('/*__ALBUM__*/', json.dumps(album_names, ensure_ascii=False))
               .replace('/*__PATHS__*/', json.dumps(paths, ensure_ascii=False))
               .replace('<!--__FONTS__-->', fonts))
    assert '/*__' not in page, 'unfilled placeholder'
    return page

# ---------- www (PWA / Android): pictures as separate files, so the page opens fast ----------
www = P('www')
shutil.rmtree(www, ignore_errors=True)
os.makedirs(os.path.join(www, 'icons')); os.makedirs(os.path.join(www, 'img'))
img_files = []
def ext_img(u):
    if not (isinstance(u, str) and u.startswith('data:image/')):
        return u
    head, b64 = u.split(',', 1)
    raw = base64.b64decode(b64)
    name = 'img/%s.%s' % (hashlib.sha1(raw).hexdigest()[:12], 'png' if 'png' in head else 'jpg')
    if name not in img_files:
        open(os.path.join(www, name), 'wb').write(raw); img_files.append(name)
    return name
images_www = {k: ext_img(v) for k, v in images_d.items()}
story_www = {pid: [dict(s, img=ext_img(s['img'])) for s in sc] for pid, sc in story_d.items()}
for f in ('icon-192.png', 'icon-512.png', 'maskable-512.png', 'apple-touch-icon.png'):
    shutil.copy(P('icons', f), os.path.join(www, 'icons', f))
pwa = ('<link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icons/apple-touch-icon.png">'
       '<link rel="icon" href="icons/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes">'
       '<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="أنشودتي">')
open(os.path.join(www, 'index.html'), 'w', encoding='utf-8').write(render(images_www, story_www).replace('<!--__PWA__-->', pwa))
json.dump({
    'name': 'أنشودتي', 'short_name': 'أنشودتي', 'description': 'مكتبة أناشيد للأطفال بصوتهم',
    'lang': 'ar', 'dir': 'rtl', 'start_url': './', 'scope': './', 'display': 'standalone',
    'background_color': '#fbf6ec', 'theme_color': '#F1E4C9', 'orientation': 'any',
    'icons': [{'src': 'icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
              {'src': 'icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
              {'src': 'icons/maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}]
}, open(os.path.join(www, 'manifest.webmanifest'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
precache = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png'] + img_files
# only this app's caches are ever deleted: the origin may host other sites of the same account
open(os.path.join(www, 'sw.js'), 'w', encoding='utf-8').write(f"""const C='anasheed-{version}';
const FILES={json.dumps(precache)};
self.addEventListener('install',e=>{{e.waitUntil(caches.open(C).then(c=>c.addAll(FILES)));self.skipWaiting()}});
self.addEventListener('activate',e=>{{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('anasheed-')&&k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))}});
// network first, but never wait more than 3 s for a slow connection
self.addEventListener('fetch',e=>{{if(e.request.method!=='GET')return;
  const cached=()=>caches.match(e.request,{{ignoreSearch:true}}).then(r=>r||caches.match('index.html'));
  const net=fetch(e.request).then(r=>{{if(r.ok){{const x=r.clone();caches.open(C).then(c=>c.put(e.request,x))}}return r}});
  e.respondWith(Promise.race([net,new Promise((_,rej)=>setTimeout(rej,3000))]).catch(()=>cached().then(r=>r||net)))}});
""")

# ---------- dist: one self-contained file (also used by the Windows app) ----------
os.makedirs(P('dist'), exist_ok=True)
open(P('dist', 'أنشودتي.html'), 'w', encoding='utf-8').write(render(images_d, story_d).replace('<!--__PWA__-->', ''))
print(f'built version {version}: www/index.html {os.path.getsize(os.path.join(www, "index.html"))//1024} KB + {len(img_files)} pictures · '
      f'dist {os.path.getsize(P("dist", "أنشودتي.html"))//1024} KB', file=sys.stderr)
