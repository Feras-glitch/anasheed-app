"""Fifth review (2026-11-05): one check for each fix. Run with the same server as tests/e2e.py."""
import asyncio, json, os, sys, tempfile
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

async def fresh(b, **kw):
    ctx = await b.new_context(viewport={'width': 360, 'height': 740}, accept_downloads=True, permissions=['microphone'], **kw)
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(URL); await pg.wait_for_timeout(700)
    return ctx, pg, errs

async def kid(pg, name, age):
    await pg.evaluate(f"kids.push('{name}'); kidInfo['{name}']={{age:{age}}}; LS.set('kids',kids); LS.set('kidInfo',kidInfo); closeSheet(); setKid('{name}'); closeSheet()")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        tmp = tempfile.mkdtemp()

        # ---- a crafted backup cannot reach the inner machinery of objects ----
        ctx, pg, errs = await fresh(b)
        await kid(pg, 'دلال', 10)
        bad = os.path.join(tmp, 'proto.json')
        open(bad, 'w', encoding='utf-8').write('{"app":"anasheed","kids":["__proto__","constructor","سارة"],"kidInfo":{"__proto__":{"age":9}},'
            '"stats":{"__proto__":{"٤":{"star":1,"mem":[0]}},"toString":{"x":{}},"دلال":{"__proto__":{"mem":[0]},"٤":{"rec":2}}},'
            '"meanings":{"__proto__":"x","٤|الثعلب":"تجربة"}}')
        await pg.evaluate("gateUntil=Date.now()+6e5"); await pg.click('#goParent'); await pg.set_input_files('#aImport', bad); await pg.wait_for_timeout(900); await pg.evaluate('closeSheet()')
        polluted = await pg.evaluate("({}).hasOwnProperty('٤') || ({})['٤']!==undefined || ({}).mem!==undefined || ({}).age!==undefined")
        check(not polluted and not errs, f'a backup with «__proto__» keys pollutes nothing {errs[:1]}')
        check(await pg.evaluate("!kids.includes('__proto__') && !kids.includes('constructor') && kids.includes('سارة')"), 'names like «__proto__» are refused, a real name is kept')
        check(await pg.evaluate("String(KS('دلال')['٤'].rec)") == '2' and await pg.evaluate("typeof String({})") == 'string', 'the real progress in the same file is merged')
        check(await pg.evaluate("okName('__proto__')===false && okName('كريم')===true"), 'okName guards typed names')

        # ---- the review schedule and the waiting takes come back with a backup ----
        due = await pg.evaluate("Date.now()+3*864e5")
        rt = os.path.join(tmp, 'rev.json')
        json.dump({'app': 'anasheed', 'stats': {'دلال': {'١٦': {'mem': [0], 'rev': {'0': {'step': 2, 'due': due}}, 'pend': [1, 0], 'last': 5}}}}, open(rt, 'w', encoding='utf-8'), ensure_ascii=False)
        await pg.set_input_files('#aImport', rt); await pg.wait_for_timeout(700); await pg.evaluate('closeSheet()')
        got = await pg.evaluate("JSON.stringify({rev:KS('دلال')['١٦'].rev, pend:KS('دلال')['١٦'].pend})")
        check(json.loads(got) == {'rev': {'0': {'step': 2, 'due': due}}, 'pend': [1]}, f'restore keeps the review schedule; a memorised segment is no longer «waiting» {got}')
        clean = await pg.evaluate("JSON.stringify(cleanRec({b64:'x',lvl:9,seg:-3,stamp:'<b>',type:'text/html',who:'__proto__',marks:[[1,2,3],'x']}))")
        c = json.loads(clean)
        check(c['lvl'] == 4 and c['seg'] == 0 and 'stamp' not in c and c['type'] == 'audio/webm' and c['who'] == '—' and c['marks'] == [[1, 2, 1]], f'a recording from a backup is kept within known values {clean}')
        await ctx.close()

        # ---- «فلسطين داري» is recognised by whole words; another poem about Palestine is not taken for it ----
        ctx, pg, errs = await fresh(b)
        await kid(pg, 'فرح', 8)
        r = await pg.evaluate("""() => { const t=(title,lines)=>!!packMap({id:'t',title,verses:lines.map(l=>l.split(' / '))});
          return {
            other: t('نشيد القدس', ['فلسطين أرض الأنبياء / نحبها', 'بلادي يا بلادي / لك قلبي', 'شعبي كريم / وأهلي', 'وجدت فيها المسجد / الجديد', 'فلسطين لنا / دائماً']),
            mosque: t('في المسجد', ['فلسطين / بلادي', 'مسجد جديد / وجدت', 'لحن الطير / غريب', 'ثمار / شعبه', 'مهد / فلسطين']),
            four: t('فلسطين داري', ['فلسطين كلمة وفؤاد صغير / لحن جميل', 'غريب الدار وثمار / الشجر', 'شعب كبير ومهدي / صغير', 'فلسطين / كلمة']),
            eight: t('أنشودة', ['فلسطين كلمة / في الدفتر','فؤاد صغير / في الصدر','لحن جميل / في الصباح','غريب الدار / بعيد','ثمار الشجر / حلوة','شعب كبير / طيب','مهدي صغير / دافئ','فلسطين كلمة / في الدفتر']),
            hit: [pHit(['مسجد'],'جد'), pHit(['جديد'],'جد'), pHit(['وجدت'],'جد'), pHit(['جدي'],'جد'), pHit(['والسليبه'],'سليب'), pHit(['ولحنا'],'لحن'), pHit(['فوادي'],'فواد')] }; }""")
        check(not r['other'] and not r['mosque'], f'another poem about Palestine, or «مسجد/جديد/وجدت», is not taken for the pack {r}')
        check(r['four'] and r['eight'], 'the pack is found in 8 short lines, or in 4 long lines under its own title')
        check(r['hit'] == [False, False, False, True, True, True, True], f'a key matches a whole word with its particles and endings {r["hit"]}')

        # ---- 🧠 after the parent stamps the whole poem recited in one go ----
        res = await pg.evaluate("""() => { const p=poemById('٣'), n=segments(p).length; const s=st('٣'); s.mem=[]; s.pend=[n]; saveS();
          stampEffects({poem:'٣',who:kid,seg:n},'ok'); const b=badges(p); const news=takeNews(kid);
          return {n, mem:b.mem, all:segments(p).every((_,i)=>st('٣').mem.includes(i)), cert:news.some(x=>x.cert&&x.whole)}; }""")
        check(res['n'] > 1 and res['mem'] and res['all'] and res['cert'], f'stamping «الكل» gives 🧠, the certificate and every segment {res}')

        # ---- reviews fall on the child's days, not 24-hour steps ----
        res = await pg.evaluate("""() => { const s={}; scheduleReview(s,0,0); const d=new Date(); d.setHours(0,0,0,0); d.setDate(d.getDate()+1);
          const s2={}; stampEffects({poem:'١٦',who:kid,seg:0},'again'); return [s.rev[0].due===d.getTime(), st('١٦').rev[0].due===d.getTime()]; }""")
        check(res == [True, True], '«tomorrow» starts at local midnight (stamp and «نراجعه غداً»)')

        # ---- meanings: a particle before «ال», and the colon that repeated the word ----
        res = await pg.evaluate("[alKey('بالزهد'), alKey('والقمر'), alKey('للعلم'), alKey('وبالسيف'), alKey('بيت'), optNorm('ابن عرس: حيوان صغير'), optNorm('بلا حذاء')]")
        check(res == ['الزهد', 'القمر', 'العلم', 'السيف', None, 'حيوان صغير', 'بلا حذاء'], f'«بالزهد» finds «الزهد»; the head before a colon is not an option {res}')
        res = await pg.evaluate("openPoem('٦'), M('فسلم',10)")
        check('استسلم' in (res or ''), f'«فسلّم» in «النملة والمقطم» means surrendered ({res})')

        # ---- a child who cannot read: no voice yet is said with a picture, and the parent's list puts that poem first ----
        await kid(pg, 'كريم', 6)
        await pg.evaluate("show('home'); renderHome(); openPoem('١٩')"); await pg.wait_for_timeout(600)
        check(await pg.is_visible('#waitModel') and 'ينتظر صوت' in await pg.text_content('#waitModel'), 'age 6, no model: «🦜⏳ ينتظر صوت بابا»')
        check(await pg.evaluate("modelOrder()[0].id") == '١٩', 'the poem the youngest found silent comes first for the parent')
        await pg.evaluate("openPoem('٧')"); await pg.wait_for_timeout(600)
        check(await pg.evaluate('mode') == 'story' and await pg.locator('#storyBox .splay:visible').count() >= 1, 'age 6: the picture story opens first, its pictures show they wait for the voice')
        icons = await pg.evaluate("kids.map(kidIcon)")
        check(len(set(icons)) == len(icons) and '👤' not in icons and icons[-1] in await pg.text_content('#kidChip'), f'each child has an animal of their own, shown by the name {icons}')
        await pg.evaluate("pKid='فرح'"); await pg.evaluate("gateUntil=Date.now()+6e5"); await pg.click('#goParent'); await pg.wait_for_timeout(400)
        await pg.evaluate("pKid='فرح'; renderParent()"); await pg.wait_for_timeout(300)
        await pg.click('#kidDel'); await pg.click('#askY'); await pg.wait_for_timeout(300)
        check(await pg.evaluate("!own(kidInfo,'فرح') && !kids.includes('فرح')"), 'deleting a child leaves nothing for a new child of the same name')
        await ctx.close()

        # ---- the save sheet: «🗑 امسح وأعد» can be undone; the record bar fits a 360 px phone ----
        ctx, pg, errs = await fresh(b)
        await kid(pg, 'دلال', 10)
        await pg.evaluate("openPoem('١٦')"); await pg.wait_for_timeout(400); await pg.click('#modeSing')
        await pg.click('#recBtn'); await pg.wait_for_timeout(2200); await pg.click('#recBtn'); await pg.wait_for_timeout(600)
        await pg.click('#redo'); await pg.wait_for_timeout(300)
        check(await pg.is_visible('#undoBtn') and not await pg.evaluate("document.querySelector('#pop').classList.contains('on')"), '«🗑 امسح وأعد» closes the sheet and offers «↩ رجّع التسجيل»')
        await pg.click('#undoBtn'); await pg.wait_for_timeout(300)
        check(await pg.locator('#keep').count() == 1 and not await pg.is_visible('#undoBtn'), 'the take comes back to be saved')
        await pg.click('#keep'); await pg.wait_for_timeout(600); await pg.evaluate('closeSheet()')
        boxes = await pg.evaluate("[...document.querySelectorAll('#bar button, #bar .rec')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect(); return [r.left,r.right,r.width,r.height]})")
        check(all(x[0] >= 0 and x[1] <= 360 for x in boxes) and all(x[2] >= 44 and x[3] >= 44 for x in boxes), f'with «▶ اسمعني» the bar fits 360 px and every button is ≥ 44 px {boxes}')
        small = await pg.evaluate("[...document.querySelectorAll('.playbar .btn')].map(e=>{ e.parentElement.style.display='flex'; const r=e.getBoundingClientRect(); return Math.min(r.width,r.height); })")
        check(all(x >= 44 for x in small), f'⏹ and 🔁 in the play bar are ≥ 44 px {small}')
        await ctx.close()

        # ---- web: a second window takes over, the first stops writing ----
        ctx = await b.new_context(viewport={'width': 390, 'height': 844})
        a = await ctx.new_page(); await a.goto(URL); await a.wait_for_timeout(600)
        bpg = await ctx.new_page(); await bpg.goto(URL); await bpg.wait_for_timeout(800)
        check(await a.locator('.tablock').count() == 1 and await a.evaluate("LS.set('x',1)") is False, 'the older window is covered and no longer saves')
        check(await bpg.locator('.tablock').count() == 0 and await bpg.evaluate("LS.set('x',1)") is True, 'the newer window works')
        await ctx.close()
        await b.close()
    print(f'{len(fails)} failures')
    sys.exit(1 if fails else 0)

asyncio.run(main())
