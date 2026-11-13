"""The fixes of the seventh review (2026-11-13) that needed no decision: the home screen of a child who cannot read, the way out
of a lost PIN and its recovery code, and the folded parent page. Run with the same server as tests/e2e.py."""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

PUT = """async (o) => { const rate=8000, secs=o.dur||4, n=rate*secs, off=new OfflineAudioContext(1,n,rate), buf=off.createBuffer(1,n,rate), d=buf.getChannelData(0);
  for(let i=0;i<n;i++) d[i]=0.3*Math.sin(2*Math.PI*300*i/rate); const blob=await bufferToWav(buf);
  return recPut(Object.assign({title:poemById(o.poem).title,when:Date.now()+Math.random(),dur:secs,blob,type:'audio/wav',lvl:4,seg:0,model:false,marks:[],loud:0.5},o)); }"""

async def kid(pg, name, age, g):
    await pg.evaluate(f"if(!kids.includes('{name}')) kids.push('{name}'); kidInfo['{name}']={{age:{age},g:'{g}'}}; LS.set('kids',kids); LS.set('kidInfo',kidInfo); closeSheet(); setKid('{name}'); closeSheet()")

async def until(pg, js, secs=20):
    # polls a (possibly async) expression until it is truthy: a slow CI machine gets the time it needs
    for _ in range(secs * 5):
        if await pg.evaluate(f"(async()=>!!({js}))()"): return True
        await pg.wait_for_timeout(200)
    return False

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 360, 'height': 740})
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(700)

        # ---- the home screen of a child who cannot read: no written filters or tags, a big 🦜 where a voice can lead him ----
        await kid(pg, 'ليلى', 10, 'g')
        await pg.evaluate("poetF='أحمد شوقي'; renderHome()")
        vis = lambda sel: f"getComputedStyle(document.querySelector('{sel}')).display!=='none'"
        check(await pg.evaluate(vis('#ages')) and await pg.evaluate(vis('#poets')), 'at ten: the age and poet filters are there')
        await kid(pg, 'يونس', 6, 'b')
        r = json.loads(await pg.evaluate(f"JSON.stringify([{vis('#ages')}, {vis('#poets')}, {vis('#grid .card .poet')}, poetF, document.querySelectorAll('#grid .card').length])"))
        check(r[0] is False and r[1] is False and r[2] is False, f'at six: no written filters, no poet line on the cards {r[:3]}')
        check(r[3] == 'all' and r[4] > 10, f'a poet filter left by an older sibling is cleared: he sees all the poems of his age ({r[4]})')
        pv = await pg.evaluate("[...document.querySelectorAll('#grid .card')][0].dataset.id")
        await pg.evaluate(PUT, {'poem': pv, 'who': 'بابا', 'model': True, 'marks': await pg.evaluate(f"poemById('{pv}').verses.map((_,i)=>[i,i,0])"), 'dur': 6})
        await pg.evaluate("renderHome()"); await pg.wait_for_timeout(400)
        r = json.loads(await pg.evaluate(f"JSON.stringify([document.querySelector('#grid .card[data-id=\"{pv}\"]').classList.contains('voiced'), getComputedStyle(document.querySelector('#grid .card[data-id=\"{pv}\"]'),'::after').content, document.querySelectorAll('#grid .card.voiced').length])"))
        check(r[0] and '🦜' in r[1] and r[2] == 1, f'the poem with a voice carries a big 🦜, and only it {r}')
        await kid(pg, 'ليلى', 10, 'g'); await pg.evaluate("ageF='all'; renderHome()"); await pg.wait_for_timeout(400)
        check(await pg.evaluate(f"document.querySelector('#grid .card[data-id=\"{pv}\"]').classList.contains('voiced') && /🦜 بصوت/.test(document.querySelector('#grid .card[data-id=\"{pv}\"] .mtag').textContent)") and await pg.evaluate(f"getComputedStyle(document.querySelector('#grid .card[data-id=\"{pv}\"]'),'::after').content") in ('none', 'normal', ''), 'an older child keeps the written tag instead')

        # ---- the PIN and its recovery code both lost: a full backup without the PINs, and nothing opens ----
        await pg.evaluate("closeSheet(); gateUntil=0; adults=[{role:'parent',name:'بابا',salt:'s9'},{role:'teacher',name:'أ. س',salt:'t1',secret:'00112233445566778899aabb'}]; adults[0].pin=pinOf('2468','s9'); adults[0].rc=pinOf('ABCD1234','s9'); adults[1].pin=pinOf('1357','t1'); saveAdults(); 0")
        await pg.evaluate(PUT, {'poem': '٣', 'who': 'ليلى', 'dur': 3})
        await pg.evaluate("window.__bk=null; shareFiles=async(items)=>{ window.__bk=await items[0].blob.text(); return true; }; (()=>{ parentGate().then(v=>window.__g=v); })()"); await pg.wait_for_timeout(150)
        await pg.click('#gForgot'); await pg.wait_for_timeout(100)
        await pg.click('#gNoRc'); await pg.wait_for_timeout(100)
        check('احذف التطبيق وثبّته' in await pg.text_content('#sheet'), 'the way out is explained: save, reinstall, restore with a new PIN')
        await pg.click('#gSave'); await until(pg, "window.__bk")
        bk = await pg.evaluate("window.__bk")
        o = json.loads(bk) if bk else {}
        ad = o.get('adults', [])
        check(bk and len(o.get('recs', [])) >= 1 and any(a['role'] == 'parent' for a in ad), 'a full backup is saved, with the recordings')
        check(all('pin' not in a and 'salt' not in a and 'rc' not in a and 'secret' not in a for a in ad), f'…without any PIN, recovery code or teacher secret {ad}')
        check(await pg.evaluate("window.__g===false && !(Date.now()<gateUntil)"), 'and the parent page stays closed')
        # the reinstall: a fresh app restores it, its voices and progress back, and the parent is asked for a new PIN
        d = tempfile.mkdtemp(); fb = os.path.join(d, 'backup.json'); open(fb, 'w', encoding='utf-8').write(bk or '{}')
        ctx2 = await b.new_context(viewport={'width': 360, 'height': 740}); p2 = await ctx2.new_page(); await p2.goto(URL); await p2.wait_for_timeout(700)
        await p2.evaluate("closeSheet(); gateUntil=Date.now()+6e5"); await p2.set_input_files('#aImport', fb)
        await until(p2, f"(await recMeta()).length>={len(o.get('recs', []))} && kids.includes('ليلى')"); await p2.wait_for_timeout(300)
        r = json.loads(await p2.evaluate("(async()=>JSON.stringify([(await recMeta()).length, kids.includes('ليلى'), adults.map(a=>a.role+':'+!!a.pin)]))()"))
        check(r[0] == len(o.get('recs', [])) and r[0] >= 2 and r[1] and r[2] == ['parent:false', 'teacher:false'], f'after reinstalling, the backup brings back every voice and child, with no PIN {r}')
        await p2.evaluate("closeSheet(); gateUntil=0; (()=>{ parentGate().then(v=>window.__g=v); })()"); await p2.wait_for_timeout(150)
        check(await p2.locator('#gateBtn').count() == 1 and await p2.locator('#gPin').count() == 0, 'the page opens again by the long press…')
        await p2.evaluate("closeSheet(); gateUntil=Date.now()+6e5; show('parent'); renderParent()"); await p2.wait_for_timeout(500)
        check(await p2.evaluate("$('#secAdults').open") and await p2.is_visible('#adultsBox .warn') and 'بلا رقم سري' in await p2.text_content('#sumAdults'), '…and the parent page asks at once for a new PIN')
        await ctx2.close()

        # ---- the parent page: rarely used parts folded under their titles, with a line on where they stand; nothing removed ----
        await pg.evaluate("gateUntil=Date.now()+6e5; show('parent'); renderParent()"); await pg.wait_for_timeout(700)
        r = json.loads(await pg.evaluate("JSON.stringify([$('#secAdults').open, $('#sumAdults').textContent, $('#secPraise').open, $('#sumPraise').textContent, $('#secAdd').open, $('#sumAdd').textContent])"))
        check(r[0] is False and 'لك رقم سري' in r[1] and 'معلّمة واحدة' in r[1], f'the adults are folded, their line says where they stand {r[:2]}')
        check(r[2] is False and r[3] == 'لا عبارات بعد', f'praise is folded {r[2:4]}')
        check(r[4] is True and 'جاهز' in r[5], f'the extra poems stay open while a ready pack waits for its text {r[4:]}')
        r = json.loads(await pg.evaluate("JSON.stringify([document.querySelectorAll('#packList details.howTo').length, Object.keys(PACKS).length, Object.values(PACKS).every(k=>!k.how || $('#packList').textContent.includes(k.how.slice(0,40)))])"))
        check(r[0] == r[1] and r[2], f'each pack\'s writing guide folds under its title, every word still there {r}')
        t = await pg.text_content('#adultsBox')
        check('بالملفات (في أي وقت)' in t and 'في الجلسة المباشرة' in t and await pg.locator('#adultsBox details.howTo').count() == 1, 'the teacher\'s two ways fold under one line, both kept')
        await pg.click('#pIndex [data-go="secPraise"]'); await pg.wait_for_timeout(300)
        check(await pg.evaluate("$('#secPraise').open"), 'the page index opens a folded section before going to it')
        await pg.click('#secAdults > summary'); await pg.wait_for_timeout(150)
        check(await pg.evaluate("$('#secAdults').open") and await pg.is_visible('#adPin'), 'a tap on its title opens it')
        # the adults open by themselves when something there needs doing
        await pg.evaluate("$('#secAdults').open=false; adults=adults.filter(a=>a.role!=='parent'); saveAdults(); renderParent()"); await pg.wait_for_timeout(500)
        check(await pg.evaluate("$('#secAdults').open") and 'بلا رقم سري' in await pg.text_content('#sumAdults'), 'with no PIN for the parent the section opens by itself')

        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print(f'\n{len(fails)} failures'); sys.exit(1 if fails else 0)

asyncio.run(main())
