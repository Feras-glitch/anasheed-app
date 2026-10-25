"""Give a poem its own card picture: python3 scripts/add_cover.py <poem id> <image> [focus] [ratio]
The home card is a wide band (about 1.8:1 to 3:1 depending on the screen), so the picture is cut to 2:1
around `focus` (0 = top of the picture, 1 = bottom; default 0.5) and saved as content/thumbs/<id>.jpg.
A wider `ratio` (e.g. 2.6) keeps a subject near the top or bottom edge on phones too.
A poem with a picture story already shows its first scene; this is for poems without one."""
import io, json, os, sys
from PIL import Image

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) not in (3, 4, 5):
    sys.exit(__doc__)
pid, src = sys.argv[1], sys.argv[2]
focus = float(sys.argv[3]) if len(sys.argv) >= 4 else 0.5
ratio = float(sys.argv[4]) if len(sys.argv) == 5 else 2.0
assert 0 <= focus <= 1, 'focus is a fraction of the height, 0..1'

im = Image.open(src).convert('RGB')
w, h = im.size
bh = min(h, int(w / ratio))
top = min(max(0, int(focus * h - bh / 2)), h - bh)
im = im.crop((0, top, w, top + bh)).resize((800, round(800 / ratio)), Image.LANCZOS)
out = os.path.join('content', 'thumbs', pid + '.jpg')
os.makedirs(os.path.join(R, 'content', 'thumbs'), exist_ok=True)
im.save(os.path.join(R, out), 'JPEG', quality=80, optimize=True)

p = os.path.join(R, 'content', 'thumbs.json')
d = json.load(open(p, encoding='utf-8'))
d[pid] = out
with open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
    f.write('\n')
print(pid, '→', out, f'{os.path.getsize(os.path.join(R, out)) // 1024} KB')
