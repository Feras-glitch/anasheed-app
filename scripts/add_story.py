"""Add a picture story: python3 scripts/add_story.py <poem id> img1 img2 img3 img4 [--verses 0,4,6,9]
Pictures are resized to 900 px JPEG and tied to the verses in docs/story_plan.json (or --verses)."""
import base64, io, json, os, sys
from PIL import Image
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
verses = None
if '--verses' in args:
    i = args.index('--verses'); verses = [int(x) for x in args[i + 1].split(',')]; del args[i:i + 2]
pid, imgs = args[0], args[1:]
if verses is None:
    verses = json.load(open(os.path.join(R, 'docs', 'story_plan.json'), encoding='utf-8'))[pid]
assert len(verses) == len(imgs), f'{len(imgs)} pictures for {len(verses)} verses'
def b64(path):
    im = Image.open(path).convert('RGB'); im.thumbnail((900, 900))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=78, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
p = os.path.join(R, 'content', 'story.json')
st = json.load(open(p, encoding='utf-8'))
st[pid] = [{'img': b64(f), 'v': v} for f, v in zip(imgs, verses)]
json.dump(st, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
print('stories:', {k: len(v) for k, v in st.items()})
