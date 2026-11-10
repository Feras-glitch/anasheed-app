"""Guard for the packs of protected poems: no three words in a row from the poem may appear in what the app ships.

The poem's words never live in this repository. The parent keeps them in a private folder, `private/<pack name>.txt`
(ignored by git), or in the «نصوصي» file the app exports. When that folder exists, build.py calls `check()` and stops the
build on any three-word run shared between the poem and the pack. The pack title and Quran quotations are exempt.

    python3 tools/textcheck.py private/            # check every pack that has a text in the folder
    python3 tools/textcheck.py نصوصي.json          # or the app's exported file
"""
import json, os, re, sys

DIAC = re.compile('[ً-ٰٟـ]')
QURAN = re.compile('﴿[^﴾]*﴾')

def norm(s):
    s = DIAC.sub('', s)
    s = re.sub('[أإآ]', 'ا', s).replace('ؤ', 'و').replace('ئ', 'ي').replace('ة', 'ه').replace('ى', 'ي')
    return re.sub('[^ء-ي ]', ' ', s)

def words(s):
    return [w[2:] if w.startswith('ال') and len(w) > 3 else w for w in norm(s).split()]  # «الحرب» and «حرب» are the same word here

def grams(s, n=3):
    w = words(s)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}

def strings(x, path=''):
    if isinstance(x, str): yield path, x
    elif isinstance(x, list):
        for i, y in enumerate(x): yield from strings(y, f'{path}[{i}]')
    elif isinstance(x, dict):
        for k, y in x.items():
            if k in ('keys', 'story', 'title', 'poet', 'age', 'path'): continue
            yield from strings(y, f'{path}.{k}' if path else k)
        if isinstance(x.get('words'), dict): yield from ((f'{path}.words', k) for k in x['words'])

def check(pack, text):
    """Every place in the pack that shares three words in a row with the poem: [(where, words)]."""
    poem = grams(text) - grams(pack.get('title', ''))
    out = []
    for where, s in strings(pack):
        for g in grams(QURAN.sub(' ', s)) & poem: out.append((where, ' '.join(g)))
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
    res = run(packs, sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'private'))
    bad = 0
    for name, hits in res.items():
        print(f'{"✗" if hits else "✓"} {name}: {len(hits)}')
        for where, g in hits: print(f'    {where}: «{g}»')
        bad += len(hits)
    print('no text to check against' if not res else f'{bad} places'); sys.exit(1 if bad else 0)
