"""The parent's decisions after the fifth review (2026-11-06): one check for each. Run with the same server as tests/e2e.py."""
import asyncio, json, sys
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

# a take as the app saves it: a tone, with the flags of its kind (memCand / review / echo)
PUT = """async (o) => { const rate=8000, secs=o.dur||4, n=rate*secs, off=new OfflineAudioContext(1,n,rate), buf=off.createBuffer(1,n,rate), d=buf.getChannelData(0);
  for(let i=0;i<n;i++) d[i]=0.3*Math.sin(2*Math.PI*300*i/rate); const blob=await bufferToWav(buf);
  return recPut(Object.assign({title:poemById(o.poem).title,when:Date.now()+Math.random(),dur:secs,blob,type:'audio/wav',lvl:4,seg:0,model:false,marks:[],loud:0.5},o)); }"""

async def fresh(b):
    ctx = await b.new_context(viewport={'width': 360, 'height': 740}, permissions=['microphone'])
    pg = await ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    await pg.goto(URL); await pg.wait_for_timeout(700)
    return ctx, pg, errs

async def kid(pg, name, age, g):
    await pg.evaluate(f"if(!kids.includes('{name}')) kids.push('{name}'); kidInfo['{name}']={{age:{age},g:'{g}'}}; LS.set('kids',kids); LS.set('kidInfo',kidInfo); closeSheet(); setKid('{name}'); closeSheet()")

async def parent(pg):
    await pg.evaluate("closeSheet(); gateUntil=Date.now()+6e5"); await pg.click('#goParent'); await pg.wait_for_timeout(700)

async def hear(pg, row):
    await pg.click(f'{row} [data-pl]'); await pg.wait_for_timeout(400)
    await pg.evaluate("document.querySelectorAll('#pQueue audio').forEach(a=>a.dispatchEvent(new Event('ended')))"); await pg.wait_for_timeout(100)

def S(k, pid):
    return f"JSON.stringify(KS('{k}')['{pid}']||{{}})"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'])

        # ---- pieces by age: three verses up to seven, four up to nine, six after ----
        ctx, pg, errs = await fresh(b)
        await kid(pg, 'دلال', 10, 'g'); await kid(pg, 'فرح', 8, 'b'); await kid(pg, 'كريم', 6, 'b')
        r = json.loads(await pg.evaluate("JSON.stringify(['كريم','فرح','دلال'].map(k=>[segSize(k), segments(poemById('٣٠'),k)]))"))
        check(r[0] == [3, [[0, 3], [3, 6], [6, 10]]], f'age 6: pieces of three, a last verse alone joins the piece before {r[0]}')
        check(r[1] == [4, [[0, 4], [4, 8], [8, 10]]], f'age 8: pieces of four {r[1]}')
        check(r[2] == [6, [[0, 10]]], f'age 10: a ten-verse poem is one piece {r[2]}')
        # ---- the young path starts with the most familiar poem, and its hint speaks to the child ----
        check(await pg.evaluate("pathOf('كريم')[0]") == '١٦' and await pg.evaluate("PATHS.young.length") == 17, 'the young path starts with «طلع البدر» (17 steps)')
        check('ردّد مع بابا' in await pg.text_content('#pathBox'), 'age 6: the path hint is «ردّد مع بابا، ثم أنشد»')
        await pg.evaluate("LS.set('parentName','ماما'); kidInfo['كريم'].g='g'; renderHome()")
        check('ردّدي مع ماما' in await pg.text_content('#pathBox'), 'the hint follows the child\'s gender and the parent\'s name')
        await pg.evaluate("LS.set('parentName',''); kidInfo['كريم'].g='b'; renderHome()")
        # the parent may arrange a child's path: here «٧» first, for the echo steps below
        await pg.evaluate("kidInfo['كريم'].path=['٧',...PATHS.young.filter(x=>x!=='٧')]; LS.set('kidInfo',kidInfo); renderHome()")

        # ---- gender: the buttons speak to a girl as a girl ----
        await pg.evaluate("setKid('دلال'); closeSheet()"); await pg.click('#grid .card[data-id="٣٠"]') if await pg.locator('#grid .card[data-id="٣٠"]').count() else await pg.evaluate("openPoem('٣٠')")
        await pg.wait_for_timeout(300)
        t = await pg.evaluate("[$('#modelBtn').textContent,$('#echoBtn').textContent,$('#modeQuiz').textContent].join('|')")
        check('اسمعي النموذج' in t and 'ردّدي بعدي' in t and 'اختبري نفسك' in t, f'a girl: «اسمعي، ردّدي، اختبري» {t}')
        await pg.evaluate("setKid('فرح'); closeSheet()"); await pg.wait_for_timeout(200)
        t = await pg.evaluate("[$('#modelBtn').textContent,$('#echoBtn').textContent,$('#modeQuiz').textContent].join('|')")
        check('اسمع النموذج' in t and 'ردّد بعدي' in t and 'اختبر نفسك' in t, f'a boy: «اسمع، ردّد، اختبر» {t}')
        await pg.evaluate("(ageSheet('سلمى'), 1)"); await pg.wait_for_timeout(200)
        check(await pg.locator('#sheet [data-g]').count() == 2, 'the age sheet asks boy or girl')
        await pg.click('#sheet [data-g="g"]'); await pg.click('#sheet [data-a="9"]'); await pg.wait_for_timeout(200)
        check(await pg.evaluate("JSON.stringify(kidInfo['سلمى'])") == '{"g":"g","age":9}', 'gender and age are kept for the child')
        check(await pg.evaluate("gw('ينشد','تنشد','سلمى')+gw('ينشد','تنشد','فرح')") == 'تنشدينشد', 'shared text: «تنشد» for a girl, «ينشد» for a boy')

        # ---- «فلسطين داري»: the trimmed glossary, the idea, and wrong meanings aligned to the parent's typed lines ----
        check(await pg.evaluate("Object.keys(PACKS['فلسطين'].words).length") == 16 and 'في قلبه' in await pg.evaluate("PACKS['فلسطين'].idea"), 'the pack keeps 16 hard words and the new idea')
        al = await pg.evaluate("""() => { if(!BW['pack:فلسطين']) BW['pack:فلسطين']=PACKS['فلسطين'].bayt.map((x,i)=>['خطأ أول '+i,'خطأ ثان '+i]);
          const lines=['فلسطين كلمة / في الدفتر','فؤاد صغير / في الصدر','لحن جميل / في الصباح','غريب الدار / بعيد','ثمار الشجر / حلوة','شعب كبير / طيب','مهدي صغير / دافئ','فلسطين كلمة / في الدفتر'];
          const p={id:'u-test',title:'فلسطين داري',verses:lines.map(l=>l.split(' / ')),poet:'—',age:[6,12]}; added.push(p); applyPacks();
          const k=PACKS['فلسطين'], ok=p.pack==='فلسطين' && BW[p.id].length===p.verses.length && BW[p.id].every((w,j)=> w===null ? BAYT[p.id].v[j]==='' : BW['pack:فلسطين'][k.bayt.indexOf(BAYT[p.id].v[j])]===w);
          added.pop(); delete BAYT[p.id]; delete BW[p.id]; return ok; }""")
        check(al, 'the wrong meanings of a pack follow the verses as the parent typed them')
        check(not errs, f'no page errors {errs[:2]}')
        await ctx.close()

        # ---- the parent's ear: the stamp waits until 70% was heard; stumbled verses are marked; ✓ vs «مع تردّد» ----
        ctx, pg, errs = await fresh(b)
        await kid(pg, 'سلمى', 9, 'g')
        await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'سلمى', 'seg': 0, 'memCand': True})
        await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'سلمى', 'seg': 1, 'memCand': True})
        await parent(pg)
        check(await pg.evaluate("[...document.querySelectorAll('#pQueue [data-st]')].every(b=>b.disabled)") and await pg.locator('#pQueue .hearFirst').count() == 2, 'every stamp waits: «اسمع أولاً، ثم احكم»')
        r0 = '#pQueue .r:has-text("الأبيات ١–٤")'
        await pg.click(f'{r0} [data-pl]'); await pg.wait_for_timeout(400)
        await pg.evaluate("(()=>{ const a=document.querySelector('#pQueue audio'); a.pause(); a.currentTime=1; })()"); await pg.wait_for_timeout(300)
        check(await pg.locator(f'{r0} [data-st="ok"]').is_disabled(), 'a quarter heard: still waiting')
        await pg.evaluate("(()=>{ const a=document.querySelector('#pQueue audio'); a.currentTime=3.2; })()"); await pg.wait_for_timeout(300)
        check(await pg.locator(f'{r0} [data-st="ok"]').is_enabled() and await pg.locator(f'{r0} .hearFirst').count() == 0, 'most of it heard: the stamps wake up')
        check(await pg.locator(f'{r0} .wv .chip[data-v]').count() == 4, 'the four verses of the piece can be marked')
        await pg.click(f'{r0} .wv .chip[data-v="1"]'); await pg.click(f'{r0} [data-st="ok"]'); await pg.wait_for_timeout(500)
        s = json.loads(await pg.evaluate(S('سلمى', '٣٠')))
        d3, d1, d7 = await pg.evaluate("[dueIn(3),dueIn(1),dueIn(7)]")
        check(0 in s.get('mem', []) and s['rev']['0'] == {'step': 1, 'due': d3}, f'«✓ حفظه»: memorised, first review in three days {s.get("rev")}')
        check(s.get('weak') == {'1': 1}, f'the stumbled verse is counted {s.get("weak")}')
        w = await pg.text_content('#pWeak')
        check('تتعثّر فيها سلمى' in w and 'البيت ٢' in w, 'the parent page lists «أبيات تتعثّر فيها سلمى»')
        r1 = '#pQueue .r:has-text("الأبيات ٥–٨")'
        await hear(pg, r1); await pg.click(f'{r1} [data-st="okw"]'); await pg.wait_for_timeout(500)
        s = json.loads(await pg.evaluate(S('سلمى', '٣٠')))
        check(1 in s.get('mem', []) and s['rev']['1'] == {'step': 0, 'due': d1}, f'«حفظه مع تردّد»: memorised, reviewed tomorrow {s["rev"].get("1")}')

        # ---- a review take waits for the parent's ear instead of moving the schedule by itself ----
        await pg.evaluate("(()=>{ const s=KS('سلمى')['٣٠']; s.rev['0'].due=Date.now()-1; s.rev['1'].due=Date.now()-1; saveS(); })()")
        check(await pg.evaluate("JSON.stringify(reviewsDue('٣٠','سلمى'))") == '[0,1]', 'both pieces are due')
        await pg.evaluate("(()=>{ const s=KS('سلمى')['٣٠']; s.rpend=[0,1]; s.rpendAt={0:Date.now(),1:Date.now()}; saveS(); })()")
        check(await pg.evaluate("reviewsDue('٣٠','سلمى').length") == 0, 'a review waiting for the parent is not asked again')
        await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'سلمى', 'seg': 0, 'review': True})
        await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'سلمى', 'seg': 1, 'review': True})
        await pg.evaluate("renderParent()"); await pg.wait_for_timeout(500)
        check(await pg.locator('#pQueue [data-st="rok"]').count() == 2 and await pg.locator('#pQueue [data-st="ok"]').count() == 0, 'a review take is judged «ثابت» or «ضعُف»')
        await hear(pg, r0); await pg.click(f'{r0} [data-st="rok"]'); await pg.wait_for_timeout(500)
        s = json.loads(await pg.evaluate(S('سلمى', '٣٠')))
        check(s.get('rpend') == [1] and s['rev']['0'] == {'step': 2, 'due': d7}, f'«ثابت»: the next review is further away {s["rev"]["0"]}')
        check('weak' not in s and (await pg.text_content('#pWeak')).strip() == '', 'a verse heard again without a stumble leaves the list')
        await hear(pg, r1); await pg.click(f'{r1} [data-st="rweak"]'); await pg.wait_for_timeout(500)
        s = json.loads(await pg.evaluate(S('سلمى', '٣٠')))
        check(not s.get('rpend') and s['rev']['1'] == {'step': 0, 'due': d1}, f'«ضعُف»: back to tomorrow {s["rev"]["1"]}')
        n = await pg.evaluate("(LS.get('news',{})['سلمى']||[]).map(x=>x.t).join(',')")
        check(n == 'mem,mem,rev,rev', f'the child is told of each stamp {n}')

        # ---- quiz: weak verses first, «نجحتِ» for a girl, the first try of the day counts ----
        await pg.evaluate("(()=>{ const s=KS('سلمى')['٣٠']; s.weak={'2':1}; saveS(); })()")
        await pg.click('#back'); await pg.evaluate("openPoem('٣٠')"); await pg.wait_for_timeout(300)
        await pg.click('#modeQuiz'); await pg.click('#quizBox [data-e="0"]'); await pg.click('#quizBox [data-q="complete"]'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("qs[0]") == 2, 'a stumbled verse comes first in «أكمل البيت»')
        nq = await pg.evaluate('qs.length')
        for _ in range(nq):
            await pg.evaluate("(()=>{ const r=cur.verses[qs[qi]][1]; [...document.querySelectorAll('#quizBox .opt')].find(b=>b.textContent===r).click(); })()"); await pg.wait_for_timeout(1000)
        t = await pg.text_content('#quizBox')
        check('نجحتِ في' in t and await pg.evaluate("st('٣٠').qz.complete") == 100, f'a girl reads «نجحتِ»; the first try counts ({nq} questions)')
        check(not errs, f'no page errors {errs[:2]}')
        await ctx.close()

        # ---- the youngest move along the path when the parent hears the echo done well ----
        ctx, pg, errs = await fresh(b)
        await kid(pg, 'كريم', 6, 'b')
        await pg.evaluate("kidInfo['كريم'].path=['٧',...PATHS.young.filter(x=>x!=='٧')]; LS.set('kidInfo',kidInfo)")  # the parent put «٧» first
        m = await pg.evaluate("segments(poemById('٧'),'كريم').length")
        for i in range(m):
            await pg.evaluate(PUT, {'poem': '٧', 'who': 'كريم', 'seg': i, 'echo': True, 'lvl': 0, 'dur': 3})
        check(not await pg.evaluate("stepDone('٧','كريم')"), 'before: the first step is open')
        await parent(pg)
        check(await pg.locator('#pQueue details .r').count() == m and await pg.locator('#pQueue details [data-st="eok"]').count() == m, f'echo sessions wait folded, with «✓ أتقنه» ({m})')
        for i in range(m):
            await pg.evaluate("document.querySelector('#pQueue details').open=true")
            await hear(pg, '#pQueue details .rlist > .r:first-child')
            await pg.click('#pQueue details [data-st="eok"]:not([disabled]) >> nth=0'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("stepDone('٧','كريم')") and sorted(json.loads(await pg.evaluate(S('كريم', '٧'))).get('echoOk')) == list(range(m)), 'every piece «أتقنه»: the step is done')
        await pg.click('#back'); await pg.wait_for_timeout(600); await pg.evaluate("closeSheet()")
        check('الخطوة ٢' in await pg.text_content('#pathBox'), 'the path moves to its second step')

        # ---- after the echo, 🎤 records from memory (level 4) ----
        await pg.evaluate("""() => { window.decodeRec=async()=>({duration:20}); window.spans=()=>cur.verses.map((_,i)=>[i,i+0.9]);
          window.halves=(b,s0,s1)=>[[s0,(s0+s1)/2],[(s0+s1)/2,s1]]; window.playBuf=()=>Promise.resolve(); window.pause=()=>Promise.resolve(); window.sessionRecorder=async()=>null; }""")
        await pg.evaluate("openPoem('٧')"); await pg.wait_for_timeout(300)
        await pg.evaluate("echoYoung({id:'x'})")
        await pg.wait_for_selector('#ecRec', timeout=8000)
        await pg.click('#ecRec'); await pg.wait_for_timeout(900)
        check(await pg.evaluate("level") == 4 and await pg.evaluate("!!rec && rec.state==='recording'"), 'after the echo, 🎤 records the piece from memory')
        await pg.click('#recBtn'); await pg.wait_for_timeout(600); await pg.evaluate("closeSheet()")

        # ---- a picture whose meaning is its own name does not count; one arrangement is asked once ----
        await pg.evaluate("openPoem('٧')"); await pg.wait_for_timeout(300)
        # (a six-year-old is asked picture questions only where the parent's voice can say them: the counting rule is checked as for a reader)
        await pg.evaluate("document.body.classList.remove('prereader')")
        await pg.click('#modeQuiz'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("trivialPic('الثعبان',2)") is False, '«الثعبان: الحيّة الكبيرة» is a real question')
        await pg.click('#quizBox [data-q="meaning"]'); await pg.wait_for_timeout(100)
        r = json.loads(await pg.evaluate("JSON.stringify(qs.map(x=>[x.k, x.cnt, !!(IMG(x.k,x.i) && trivialPic(x.k,x.i))]))"))
        check(all(c == (not t) for _, c, t in r) and any(t for *_, t in r), f'«٧»: a picture that names itself is practice, the other questions count {r}')
        await pg.evaluate("qs=qs.slice(0,2).map(x=>Object.assign(x,{cnt:false})).concat(qs.slice(2,3)); beginCount()")
        check(await pg.evaluate("qWhy==='few' && !qCounts"), 'fewer than three questions that count: the quiz is practice')
        await pg.evaluate("quizMenu()"); await pg.wait_for_timeout(100)
        await pg.evaluate("document.body.classList.remove('prereader')")  # (a six-year-old sees no written quizzes; the rule is checked as for a reader)
        if await pg.locator('#quizBox [data-q="order"]').count():
            await pg.click('#quizBox [data-q="order"]'); await pg.wait_for_timeout(100)
            check(await pg.evaluate("new Set(qs.map(q=>q[0])).size===qs.length"), f'each arrangement is asked once ({await pg.evaluate("qs.length")})')
        await pg.evaluate("openPoem('٣٠'); seg=0; renderSegs(); renderVerses(); mode='quiz'; quizMenu()"); await pg.wait_for_timeout(100)
        check('(تدريب)' in await pg.text_content('#quizBox [data-q="order"]'), 'a piece of three verses has one arrangement: marked as practice')
        check(not errs, f'no page errors {errs[:2]}')
        await ctx.close()
        await b.close()
    print(f'\n{len(fails)} failures'); sys.exit(1 if fails else 0)

asyncio.run(main())
