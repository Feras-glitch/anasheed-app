"""Guard for the packs of protected poems: no three words in a row from the poem may appear in what the app ships.

The poem's words never live in this repository. The parent keeps them in a private folder, `private/<pack name>.txt`
(ignored by git), or in the «نصوصي» file the app exports. When that folder exists, build.py calls `check()` and stops the
build on any three-word run shared between the poem and the pack. The pack title and Quran quotations are exempt.

So that the guard also runs where the texts are not (the public build), each run of three words is kept as a fingerprint:
a salted hash, cut short, in content/fingerprints.json. A fingerprint names no word and gives no order; it only answers
«is this run of three words one of the poem's?». build.py checks every pack and every text file of the repository against
them on every build, and names only where a run was found, never its words.

    python3 tools/textcheck.py private/                       # check every pack that has a text in the folder
    python3 tools/textcheck.py نصوصي.json                     # or the app's exported file
    python3 tools/textcheck.py --fingerprints نصوصي.json      # write the fingerprints of the packs found in the file
"""
import hashlib, json, os, re, secrets, sys

DIAC = re.compile('[ً-ٰٟـ]')
QURAN = re.compile('﴿[^﴾]*﴾')

def norm(s):
    s = DIAC.sub('', s)
    s = re.sub('[أإآ]', 'ا', s).replace('ؤ', 'و').replace('ئ', 'ي').replace('ة', 'ه').replace('ى', 'ي')
    return re.sub('[^ء-ي ]', ' ', s)

PFX = re.compile('^(?:[وف]?(?:[بكل]?ال|لل)|[وف][بكل]?|[بكل])(?=...)')
def words(s):
    # «والحرب»، «فالحرب»، «بالحرب»، «للحرب»، «وحرب» are all «حرب» here: a copied run is found whatever particle starts it
    return [PFX.sub('', w) if len(w) > 3 else w for w in norm(s).split()]

def grams(s, n=3):
    w = words(s)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}

def strings(x, path=''):
    if isinstance(x, str): yield path, x
    elif isinstance(x, list):
        for i, y in enumerate(x): yield from strings(y, f'{path}[{i}]')
    elif isinstance(x, dict):
        for k, y in x.items():
            # only the pack's own title, poet and matching data are skipped: the titles of ideas and tales are checked
            if not path and k in ('keys', 'story', 'title', 'poet', 'age', 'path'): continue
            yield from strings(y, f'{path}.{k}' if path else k)
        if isinstance(x.get('words'), dict): yield from ((f'{path}.words', k) for k in x['words'])

def check(pack, text):
    """Every place in the pack that shares three words in a row with the poem: [(where, words)]."""
    poem = grams(text) - grams(pack.get('title', ''))
    out = []
    for where, s in strings(pack):
        for g in grams(QURAN.sub(' ', s)) & poem: out.append((where, ' '.join(g)))
    return out

def fp(gram, salt):
    return hashlib.sha256((salt + '|' + ' '.join(gram)).encode('utf-8')).hexdigest()[:16]

def fingerprints(pack, text, salt):
    """The poem's runs of three words (without those of the pack's title), as fingerprints: sorted, so their order is lost."""
    return sorted({fp(g, salt) for g in grams(text) - grams(pack.get('title', ''))})

def check_fp(pack, hs, salt):
    """Every place in the pack holding a run of three words whose fingerprint is the poem's: [(where, how many)]."""
    hs = set(hs); out = []
    for where, s in strings(pack):
        n = sum(1 for g in grams(QURAN.sub(' ', s)) if fp(g, salt) in hs)
        if n: out.append((where, n))
    return out

TEXT = ('.md', '.json', '.py', '.html', '.js', '.txt', '.yml', '.yaml', '.css', '.csv')
SKIP = {'.git', 'www', 'dist', 'deps', 'node_modules', 'private', 'android', 'out', '__pycache__'}
def repo_files(root):
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP and not x.startswith('.')]
        for f in fs:
            if f.endswith(TEXT) and f != 'fingerprints.json': yield os.path.join(d, f)

def scan(root, fps, salt, packs_file):
    """Every text file of the repository (the packs file by its fields: its keys are single words) against all the
    fingerprints: [(file, pack, how many)]. The words are never returned."""
    every = {h: name for name, hs in fps.items() for h in hs}; out = []
    for f in repo_files(root):
        if os.path.abspath(f) == os.path.abspath(packs_file): continue
        try: s = open(f, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError): continue
        found = {}
        for g in grams(QURAN.sub(' ', s)):
            n = every.get(fp(g, salt))
            if n: found[n] = found.get(n, 0) + 1
        out += [(os.path.relpath(f, root), n, c) for n, c in found.items()]
    return out

def texts_from(src):
    if os.path.isdir(src):
        return {f[:-4]: open(os.path.join(src, f), encoding='utf-8').read() for f in os.listdir(src) if f.endswith('.txt')}
    d = json.load(open(src, encoding='utf-8'))  # the app's «نصوصي» export: {"poems": [{title, poet, verses:[[a,b],…]}]}
    return {p['title']: '\n'.join(' '.join(v) for v in p['verses']) for p in d.get('poems', [])}

def run(packs, src):
    """{pack name: [(where, words)]} for the packs that have a text in src. A text is matched to a pack by its title."""
    t = {norm(k).strip(): v for k, v in texts_from(src).items()}
    found = {}
    for name, k in packs.items():
        text = t.get(norm(name).strip()) or t.get(norm(k.get('title', '')).strip())
        if text: found[name] = check(k, text)
    return found

if __name__ == '__main__':
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    packs = {k: v for k, v in json.load(open(os.path.join(here, 'content', 'packs.json'), encoding='utf-8')).items() if not k.startswith('_')}
    if len(sys.argv) > 2 and sys.argv[1] == '--fingerprints':
        # the fingerprints of every pack whose poem is in the file or folder; the others keep theirs
        out = os.path.join(here, 'content', 'fingerprints.json')
        old = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {}
        salt = old.get('_salt') or secrets.token_hex(16); fps = old.get('packs', {})
        t = {norm(k).strip(): v for k, v in texts_from(sys.argv[2]).items()}
        for name, k in packs.items():
            text = t.get(norm(name).strip()) or t.get(norm(k.get('title', '')).strip())
            if text: fps[name] = fingerprints(k, text, salt); print(f'✓ {name}: {len(fps[name])} fingerprints')
            elif name not in fps: print(f'… {name}: no text in the file')
        done = all(n in fps for n in packs)
        note = 'Salted, shortened hashes of each run of three words of the protected poems (tools/textcheck.py): no word, no order.' + (' Strict: a pack without fingerprints stops the build.' if done else '')
        body = ',\n'.join(f'  {json.dumps(n, ensure_ascii=False)}: {json.dumps(fps[n])}' for n in sorted(fps))
        open(out, 'w', encoding='utf-8').write(f'{{\n "_note": {json.dumps(note)},\n "_salt": "{salt}",\n "_strict": {json.dumps(done)},\n "packs": {{\n{body}\n }}\n}}\n')
        print(f'{out}: {len(fps)} of {len(packs)} packs' + (' — every pack: the build is strict now' if done else '')); sys.exit(0)
    res = run(packs, sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'private'))
    bad = 0
    for name in packs:
        if name not in res: print(f'… {name}: no text to check against')
    for name, hits in res.items():
        print(f'{"✗" if hits else "✓"} {name}: {len(hits)}')
        for where, g in hits: print(f'    {where}: «{g}»')
        bad += len(hits)
    print('no text to check against' if not res else f'{bad} places'); sys.exit(1 if bad else 0)
