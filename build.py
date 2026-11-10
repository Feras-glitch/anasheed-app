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
        if re.match(r'(المصدر|ملاحظة|حاشية|مقتطف|http)', l) or 'http' in l:
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
# «معنى البيت»: one plain line per verse shown in the app (excerpts included), and the poem's idea
bayt = {k: v for k, v in json.load(open(P('content', 'bayt.json'), encoding='utf-8')).items() if not k.startswith('_')}
for pid, b in bayt.items():
    p = next((x for x in poems if x['id'] == pid), None)
    assert p and b.get('idea') and len(b['v']) == len(p['verses']) and all(isinstance(x, str) and x.strip() for x in b['v']), f'bayt.json: {pid} does not match its verses'
assert set(paths) == {'young', 'old'} and all(any(p['id'] == i for p in poems) for v in paths.values() for i in v), 'paths.json: unknown poem id'
G.update(OVR)
for k, v in G_PARENT.items():
    G.setdefault(k, v)
story_d = json.load(open(P('content', 'story.json'), encoding='utf-8'))
for pid, sc in story_d.items():
    p = next((x for x in poems if x['id'] == pid), None)
    assert p and sc and all(0 <= s['v'] < len(p['verses']) for s in sc), f'story {pid} is empty or points to a missing verse'
    assert all(isinstance(s.get('img'), str) and s['img'].startswith('data:image/') for s in sc), f'story {pid}: a picture is not an image'
    assert len({s['v'] for s in sc}) == len(sc), f'story {pid}: two pictures on one verse'
lessons = {k: v for k, v in json.load(open(P('content', 'lessons.json'), encoding='utf-8')).items() if not k.startswith('_')}
assert all(isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v) for v in lessons.values()), 'lessons.json: each poem has a list of questions'
assert all(any(p['id'] == k for p in poems) for k in lessons), 'lessons.json: unknown poem id'
# ready packs for protected poems the parent types in by hand: everything around the poem, never its words
packs = {k: v for k, v in json.load(open(P('content', 'packs.json'), encoding='utf-8')).items() if not k.startswith('_')}
for name, k in packs.items():
    n = len(k['keys'])
    assert k.get('title') and k.get('idea') and n >= 4 and all(isinstance(x, list) and x for x in k['keys']), f'packs.json: {name} needs title, idea and keys'
    assert len(k['bayt']) == n and all(isinstance(x, str) and x.strip() for x in k['bayt']), f'packs.json: {name}: one meaning per verse'
    assert all(0 <= s['v'] < n and os.path.exists(P(s['img'])) for s in k.get('story', [])), f'packs.json: {name}: a scene points to a missing verse or picture'
    assert not set(k.get('path', [])) - {'young', 'old'}, f'packs.json: {name}: path is young/old'
    # the fields the app reads as they are: a wrong shape would only fail on a child's tap
    assert isinstance(k.get('age', [6, 12]), list) and len(k.get('age', [6, 12])) == 2 and all(isinstance(a, int) and 5 <= a <= 12 for a in k.get('age', [6, 12])) and k.get('age', [6, 12])[0] <= k.get('age', [6, 12])[1], f'packs.json: {name}: age is [from, to] within 5–12'
    assert all(isinstance(k.get(f, ''), str) for f in ('how', 'poet', 'idea')), f'packs.json: {name}: how, poet and idea are text'
    assert all(isinstance(k.get(f, []), list) and all(isinstance(x, str) and x.strip() for x in k.get(f, [])) for f in ('lessons', 'acts')), f'packs.json: {name}: lessons and acts are lists of text'
    assert 'tale' not in k or (isinstance(k['tale'].get('title'), str) and isinstance(k['tale'].get('text'), list) and all(isinstance(x, str) for x in k['tale']['text'])), f'packs.json: {name}: tale has a title and a list of paragraphs'
    # keys are compared after the app's normalisation (no hamza forms, ة→ه, ى→ي): a key written otherwise would never match
    assert all(re.fullmatch('[ابتثجحخدذرزسشصضطظعغفقكلمنهوي]+', w) for x in k['keys'] for w in x), f'packs.json: {name}: a key is not normalised'
    assert len({s['v'] for s in k.get('story', [])}) == len(k.get('story', [])), f'packs.json: {name}: two pictures on one verse'
    assert all(isinstance(w, str) and isinstance(m, str) and m.strip() for w, m in k.get('words', {}).items()), f'packs.json: {name}: a word without meaning'
    if 'lesson' in k:  # the whole lesson: its ideas cover the verses in order, and every analysed line lies inside its idea
        ls = k['lesson']; parts = ls.get('parts', [])
        assert parts and parts[0]['from'] == 0 and parts[-1]['to'] == n and all(a['to'] == b['from'] for a, b in zip(parts, parts[1:])), f'packs.json: {name}: lesson ideas must cover verses 0..{n} in order'
        for pt in parts:
            assert pt.get('title') and pt['from'] < pt['to'], f'packs.json: {name}: an idea without title or verses'
            assert all(pt['from'] <= j < pt['to'] and notes and all(isinstance(x, str) and x.strip() for x in notes) for j, notes in pt.get('art', [])), f'packs.json: {name}: «{pt["title"]}»: analysis on a line outside the idea'
            assert all(len(qa) == 2 and all(isinstance(x, str) and x.strip() for x in qa) for qa in pt.get('discuss', [])), f'packs.json: {name}: «{pt["title"]}»: a question without its answer'
            assert all(len(wm) == 2 and wm[1].strip() for wm in pt.get('words', [])), f'packs.json: {name}: «{pt["title"]}»: a word without meaning'
        assert all(g.get('h') and g.get('a') for g in ls.get('book', [])), f'packs.json: {name}: textbook answers need a heading'
    k['story'] = [dict(s, img='data:image/jpeg;base64,' + base64.b64encode(open(P(s['img']), 'rb').read()).decode()) for s in k.get('story', [])]
# no three words in a row from a protected poem: checked when the parent's private texts are on this machine (never in git)
if os.path.isdir(P('private')):
    sys.path.insert(0, P('tools')); import textcheck
    hits = {n: h for n, h in textcheck.run({k: v for k, v in packs.items()}, P('private')).items() if h}
    assert not hits, 'packs.json: words copied from the poem: ' + '; '.join(f'{n} {w} «{g}»' for n, h in hits.items() for w, g in h[:5])
# «ما معنى البيت؟»: two wrong meanings per verse, about that verse itself, so the words of the verse do not give the answer away
bwrong = {}
if os.path.exists(P('content', 'bayt_wrong.json')):
    bwrong = {k: v for k, v in json.load(open(P('content', 'bayt_wrong.json'), encoding='utf-8')).items() if not k.startswith('_')}
for pid, ws in bwrong.items():
    right = packs[pid[5:]]['bayt'] if pid.startswith('pack:') and pid[5:] in packs else bayt[pid]['v'] if pid in bayt else None
    assert right is not None, f'bayt_wrong.json: unknown poem {pid}'
    assert len(ws) == len(right), f'bayt_wrong.json: {pid}: two wrong meanings for each verse ({len(ws)} ≠ {len(right)})'
    for r, w in zip(right, ws):
        assert isinstance(w, list) and len(w) == 2 and all(isinstance(x, str) and x.strip() and x != r for x in w) and w[0] != w[1], f'bayt_wrong.json: {pid}: a bad pair {w}'

# ---------- fonts ----------
FS = P('fonts', 'node_modules', '@fontsource')
def font_css():
    if not os.path.isdir(os.path.join(FS, 'amiri')):
        # a release must carry its fonts: an offline children's app does not call Google
        assert os.environ.get('CI') != 'true', 'fonts: not installed in CI (fonts/node_modules/@fontsource) — the release would call Google Fonts'
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
                # only the @font-face rules of the package reach the page: nothing else from a downloaded file runs in the app
                faces = re.findall(r'@font-face\s*\{[^{}]*\}', c)
                assert faces and all(re.search(r'url\(data:font/woff2;base64,[A-Za-z0-9+/=]+\)', f) and 'url(http' not in f and 'expression' not in f for f in faces), f'fonts: unexpected CSS in {css}'
                out.append('\n'.join(faces))
    print(f'fonts: embedded {len(out)} faces', file=sys.stderr)
    return '<style>' + '\n'.join(out) + '</style>'

version = os.environ.get('APP_VERSION') or datetime.date.today().isoformat()
tpl = open(P('src', 'template.html'), encoding='utf-8').read()
fonts = font_css()
def jdump(o):
    return json.dumps(o, ensure_ascii=False).replace('</', '<\\/').replace('<!--', '<\\!--')


def render(images, story, packs):
    page = (tpl.replace('/*__VERSION__*/', version)
               .replace('/*__PACKS__*/', jdump(packs))
               .replace('/*__POEMS__*/', jdump(poems))
               .replace('/*__MEANINGS__*/', jdump(G))
               .replace('/*__IMAGES__*/', jdump(images))
               .replace('/*__STORY__*/', jdump(story))
               .replace('/*__LESSONS__*/', jdump(lessons))
               .replace('/*__ALBUM__*/', jdump(album_names))
               .replace('/*__PATHS__*/', jdump(paths))
               .replace('/*__BAYT__*/', jdump(bayt))
               .replace('/*__BWRONG__*/', jdump(bwrong))
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
packs_www = {name: dict(k, story=[dict(s, img=ext_img(s['img'])) for s in k.get('story', [])]) for name, k in packs.items()}
for f in ('icon-192.png', 'icon-512.png', 'maskable-512.png', 'apple-touch-icon.png'):
    shutil.copy(P('icons', f), os.path.join(www, 'icons', f))
pwa = ('<link rel="manifest" href="manifest.webmanifest"><link rel="apple-touch-icon" href="icons/apple-touch-icon.png">'
       '<link rel="icon" href="icons/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes">'
       '<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="أنشودتي">')
open(os.path.join(www, 'index.html'), 'w', encoding='utf-8').write(render(images_www, story_www, packs_www).replace('<!--__PWA__-->', pwa))
json.dump({
    'name': 'أنشودتي', 'short_name': 'أنشودتي', 'description': 'مكتبة أناشيد للأطفال بصوتهم',
    'lang': 'ar', 'dir': 'rtl', 'start_url': './', 'scope': './', 'display': 'standalone',
    'background_color': '#fbf6ec', 'theme_color': '#F1E4C9', 'orientation': 'any',
    'icons': [{'src': 'icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
              {'src': 'icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
              {'src': 'icons/maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'}]
}, open(os.path.join(www, 'manifest.webmanifest'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
shell = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png']
assert all(f.startswith('img/') for f in img_files), 'pictures live under img/'
# the app shell is cached per version; the pictures (content-hashed names) live in one lasting cache and are fetched only once:
# an update does not download 11 MB of pictures again. Only this app's caches are ever deleted: the origin may host other sites.
open(os.path.join(www, 'sw.js'), 'w', encoding='utf-8').write(f"""const C='anasheed-{version}', IMG='anasheed-img';
const SHELL={json.dumps(shell)}, PICS={json.dumps(img_files)};
self.addEventListener('install',e=>{{e.waitUntil(Promise.all([
  caches.open(C).then(c=>c.addAll(SHELL)),
  // a picture already kept is not fetched again; one that fails does not stop the others
  caches.open(IMG).then(c=>Promise.all(PICS.map(f=>c.match(f).then(r=>r||fetch(f).then(x=>x.ok?c.put(f,x):0).catch(()=>0)))))
]));self.skipWaiting()}});
self.addEventListener('activate',e=>{{e.waitUntil(Promise.all([
  caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith('anasheed-')&&k!==C&&k!==IMG).map(k=>caches.delete(k)))),
  caches.open(IMG).then(c=>c.keys().then(rs=>{{const keep=new Set(PICS.map(f=>new URL(f,self.registration.scope).href));return Promise.all(rs.filter(r=>!keep.has(r.url)).map(r=>c.delete(r)))}}))
]).then(()=>self.clients.claim()))}});
self.addEventListener('fetch',e=>{{if(e.request.method!=='GET')return; const u=new URL(e.request.url);
  // pictures: from the lasting cache first (their names change when they change)
  if(u.origin===location.origin&&u.pathname.includes('/img/')){{e.respondWith(caches.open(IMG).then(c=>c.match(e.request,{{ignoreSearch:true}}).then(r=>r||fetch(e.request).then(x=>{{if(x.ok)c.put(e.request,x.clone());return x}}))));return}}
  // the rest: network first, but never wait more than 3 s for a slow connection; the page itself falls back to the kept copy
  const cached=()=>caches.match(e.request,{{ignoreSearch:true}}).then(r=>r||(e.request.mode==='navigate'?caches.match('index.html'):undefined));
  const net=fetch(e.request).then(r=>{{if(r.ok){{const x=r.clone();caches.open(C).then(c=>c.put(e.request,x))}}return r}});
  e.respondWith(Promise.race([net,new Promise((_,rej)=>setTimeout(rej,3000))]).catch(()=>cached().then(r=>r||net)))}});
""")

# ---------- dist: one self-contained file (also used by the Windows app) ----------
os.makedirs(P('dist'), exist_ok=True)
open(P('dist', 'أنشودتي.html'), 'w', encoding='utf-8').write(render(images_d, story_d, packs).replace('<!--__PWA__-->', ''))
print(f'built version {version}: www/index.html {os.path.getsize(os.path.join(www, "index.html"))//1024} KB + {len(img_files)} pictures · '
      f'dist {os.path.getsize(P("dist", "أنشودتي.html"))//1024} KB', file=sys.stderr)
