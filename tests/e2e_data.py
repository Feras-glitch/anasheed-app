"""Data safety: upgrading old storage, split backups, merging, and hostile or broken backup files.
Run with the same server as tests/e2e.py."""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

TONE = """async ([who, poem, secs]) => { const rate=8000, n=rate*secs, off=new OfflineAudioContext(1,n,rate), buf=off.createBuffer(1,n,rate), d=buf.getChannelData(0);
  for(let i=0;i<n;i++) d[i]=0.3*Math.sin(2*Math.PI*300*i/rate); const blob=await bufferToWav(buf);
  return recPut({poem,title:poemById(poem).title,who,when:Date.now()+Math.random(),dur:secs,blob,type:'audio/wav',lvl:1,seg:0,model:false,marks:[[0,0]],loud:0.5}); }"""

async def fresh(b):
    ctx = await b.new_context(viewport={'width': 390, 'height': 844}, accept_downloads=True)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    return ctx, pg, errs

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        tmp = tempfile.mkdtemp()

        # ---- an install from before this version (IndexedDB v1, unprefixed keys) upgrades without losing anything ----
        ctx, pg, errs = await fresh(b)
        await pg.goto(URL.replace('index.html', 'manifest.webmanifest'))
        await pg.evaluate("""() => new Promise(res => { const r = indexedDB.open('anasheed', 1);
          r.onupgradeneeded = e => e.target.result.createObjectStore('rec', {keyPath:'id', autoIncrement:true});
          r.onsuccess = e => { const db = e.target.result, tx = db.transaction('rec', 'readwrite'), s = tx.objectStore('rec');
            for (const w of [1, 2]) s.put({poem:'١', title:'الثعلب والديك', who:'هند', when:w, dur:3, buf:new Uint8Array(4000).buffer, type:'audio/webm', lvl:1, seg:0, model:false, marks:[[0,0]]});
            tx.oncomplete = () => { db.close(); res(); }; }; })""")
        await pg.evaluate("localStorage.setItem('kids', JSON.stringify(['هند'])); localStorage.setItem('kid', JSON.stringify('هند')); localStorage.setItem('stats2', JSON.stringify({'هند':{'١':{rec:2,lvl:1,heard:1}}}))")
        await pg.goto(URL); await pg.wait_for_timeout(800)
        check('هند' in await pg.text_content('#kidChip'), 'old profile carried over to the prefixed keys')
        meta = await pg.evaluate('recMeta().then(a=>a.map(r=>[r.who,r.size]))')
        check(len(meta) == 2 and all(m[1] == 4000 for m in meta), f'old recordings indexed on upgrade {meta}')
        check(await pg.evaluate('recAll().then(a=>a.length)') == 2, 'old recordings still there')
        check(await pg.locator('#grid .card[data-id="١"] .badges span.on').count() == 2, 'old progress kept')
        await ctx.close()

        # ---- a split backup (forced small parts) restores every recording into a fresh install ----
        ctx, pg, errs = await fresh(b)
        await pg.goto(URL); await pg.wait_for_timeout(500)
        await pg.evaluate("kids.push('ليلى'); LS.set('kids',kids); closeSheet(); setKid('ليلى'); gateUntil=Date.now()+6e5")
        for i in range(3): await pg.evaluate(TONE, ['ليلى', '٤', 2])
        await pg.evaluate("st('٨').mem=[0,1]; st('٨').rec=5; st('٨').last=Date.now(); saveS(); window.__bkPart=60000")
        downloads = []
        pg.on('download', lambda d: downloads.append(d))
        await pg.click('#goParent'); await pg.click('#aExport'); await pg.click('#exAll'); await pg.wait_for_timeout(3000)
        paths = []
        for d in downloads:
            pth = os.path.join(tmp, d.suggested_filename); await d.save_as(pth); paths.append(pth)
        check(len(paths) >= 2 and all('جزء' in os.path.basename(x) for x in paths), f'a large backup is split into parts {[os.path.basename(x) for x in paths]}')
        check(all(json.load(open(x, encoding='utf-8'))['app'] == 'anasheed' for x in paths), 'every part is a valid backup file')
        await ctx.close()

        ctx, pg, errs = await fresh(b)
        await pg.goto(URL); await pg.wait_for_timeout(500)
        await pg.evaluate("kids.push('ليلى'); LS.set('kids',kids); closeSheet(); setKid('ليلى'); st('٨').mem=[2]; st('٨').rec=9; st('٨').quiz=100; st('٨').last=Date.now()+1e6; saveS(); gateUntil=Date.now()+6e5")
        await pg.click('#goParent'); await pg.set_input_files('#aImport', paths); await pg.wait_for_timeout(2500)
        check(await pg.evaluate('recMeta().then(a=>a.length)') == 3, 'all recordings restored from the parts')
        s8 = await pg.evaluate("st('٨')")
        check(sorted(s8['mem']) == [0, 1, 2] and s8['rec'] == 9 and s8['quiz'] == 100, f'an older backup never wipes newer progress {s8}')
        await pg.set_input_files('#aImport', paths); await pg.wait_for_timeout(2000)
        check(await pg.evaluate('recMeta().then(a=>a.length)') == 3, 'importing the same backup twice adds nothing')

        # ---- hostile and broken files ----
        other = os.path.join(tmp, 'package.json'); json.dump({'name': 'x', 'version': '1.0.0'}, open(other, 'w'))
        await pg.set_input_files('#aImport', other); await pg.wait_for_timeout(500)
        check('ليس ملف' in await pg.text_content('#toast'), 'a JSON file that is not a backup is refused')
        evil = os.path.join(tmp, 'evil.json')
        json.dump({'app': 'anasheed', 'v': 4, 'kids': ['ليلى'],
                   'stats': {'ليلى': {'٤': {'rec': '<img src=x onerror=window.__pw=1>', 'quiz': '<img src=x onerror=window.__pw=1>', 'heard': 1}}},
                   'kidInfo': {'ليلى': {'age': '<img src=x onerror=window.__pw=1>'}},
                   'added': [{'id': 'u1', 'title': 'بلا عمر', 'verses': [['أ', 'ب']]},
                             {'id': 'u2', 'title': '<img src=x onerror=window.__pw=1>', 'poet': 'س', 'age': ['<b>', 9], 'verses': [['أ', 'ب']]},
                             {'id': 'u3', 'title': 'سليم', 'poet': 'س', 'age': [6, 9], 'verses': [['شطر', 'شطر']]}]}, open(evil, 'w'), ensure_ascii=False)
        await pg.set_input_files('#aImport', evil); await pg.wait_for_timeout(800)
        await pg.click('#back'); await pg.wait_for_timeout(300)
        n = await pg.locator('#grid .card').count()
        check(n == 32, f'broken poems in a backup are skipped, the valid one added, home not blank ({n} cards)')
        await pg.evaluate("gateUntil=Date.now()+6e5"); await pg.click('#goParent'); await pg.wait_for_timeout(500)
        await pg.reload(); await pg.wait_for_timeout(700)
        check(await pg.locator('#grid .card').count() == 32, 'home still full after a reload')
        await pg.evaluate("gateUntil=Date.now()+6e5"); await pg.click('#goParent'); await pg.wait_for_timeout(500)
        check(not await pg.evaluate('window.__pw'), 'numbers in a backup cannot inject script')

        # ---- a model saved for one segment does not play on another ----
        await pg.evaluate("recPut({poem:'٨',title:'أم اليتيم',who:'بابا',when:1,dur:3,blob:new Blob([new Uint8Array(100)]),type:'audio/webm',lvl:1,seg:0,model:true,marks:[[0,0]],loud:1})")
        await pg.click('#back'); await pg.click('#grid .card[data-id="٨"]'); await pg.wait_for_timeout(300)
        await pg.click('#segBox .chip[data-s="0"]'); await pg.wait_for_timeout(300)
        m0 = await pg.is_visible('#modelBtn')
        await pg.click('#segBox .chip[data-s="3"]'); await pg.wait_for_timeout(300)
        check(m0 and not await pg.is_visible('#modelBtn'), 'a model for segment 1 is offered there only')
        check(not errs, f'no JS errors {errs}')
        await ctx.close()

        # ---- the service worker only clears this app's caches ----
        sw = open(os.path.join(os.path.dirname(__file__), '..', 'www', 'sw.js'), encoding='utf-8').read()
        check("k.startsWith('anasheed-')" in sw, 'service worker leaves other sites\' caches alone')
        await b.close()
    print(f'\n{len(fails)} failures'); sys.exit(1 if fails else 0)

asyncio.run(main())
