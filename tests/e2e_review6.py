"""The fixes of the sixth review (2026-11-10): one check for each. Run with the same server as tests/e2e.py.
Pack poems are typed as dummy lines made of the pack's key words only — never the poem."""
import asyncio, json, sys
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

PACKS = json.load(open('content/packs.json', encoding='utf-8'))
PUT = """async (o) => { const rate=8000, secs=o.dur||4, n=rate*secs, off=new OfflineAudioContext(1,n,rate), buf=off.createBuffer(1,n,rate), d=buf.getChannelData(0);
  for(let i=0;i<n;i++) d[i]=0.3*Math.sin(2*Math.PI*300*i/rate); const blob=await bufferToWav(buf);
  return recPut(Object.assign({title:poemById(o.poem).title,when:Date.now()+Math.random(),dur:secs,blob,type:'audio/wav',lvl:4,seg:0,model:false,marks:[],loud:0.5},o)); }"""

async def kid(pg, name, age, g):
    await pg.evaluate(f"if(!kids.includes('{name}')) kids.push('{name}'); kidInfo['{name}']={{age:{age},g:'{g}'}}; LS.set('kids',kids); LS.set('kidInfo',kidInfo); closeSheet(); setKid('{name}'); closeSheet()")

async def typed(pg, title, poet, lines):
    await pg.evaluate("([a,b,t])=>{ closeSheet(); $('#aTitle').value=a; $('#aPoet').value=b; $('#aText').value=t; $('#aSave').click(); }", [title, poet, '\n'.join(lines)])
    await pg.wait_for_timeout(300)
    return await pg.evaluate("added[added.length-1].id")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 360, 'height': 740})
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(700)

        # ---- H1: a birthday does not move the child's progress ----
        await kid(pg, 'كريم', 7, 'b')
        await pg.evaluate("st('٦').mem=[3]; saveS()")
        r = json.loads(await pg.evaluate("JSON.stringify([segments(poemById('٦')).length, badges(poemById('٦')).mem, st('٦').z])"))
        check(r == [4, False, 3], f'age 7: «٦» in four segments, one memorised, not the whole {r}')
        await pg.evaluate("kidInfo['كريم'].age=8; LS.set('kidInfo',kidInfo)")
        r = json.loads(await pg.evaluate("JSON.stringify([segments(poemById('٦')).length, badges(poemById('٦')).mem, segName({poem:'٦',who:'كريم',seg:3})])"))
        check(r[0] == 4 and r[1] is False and 'الأبيات' in r[2], f'age 8: the begun poem keeps its four segments, no false 🧠 {r}')
        check(await pg.evaluate("segments(poemById('٣٠')).length") == 3 and await pg.evaluate("segSize()") == 4, 'a poem not begun yet gets the new age\'s segments')

        # ---- H2: one typo carrying a later key word does not shift the meanings ----
        W = PACKS['وصية لاجئ']
        lines = [f"{' '.join(k)} سطر / تجريبي {i + 1}" for i, k in enumerate(W['keys'])]
        lines[1] = f"كلمه{W['keys'][6][0]} {W['keys'][6][0]} سطر / تجريبي ٢"
        pid = await typed(pg, 'وصية لاجئ', 'هاشم الرفاعي', lines)
        mp = json.loads(await pg.evaluate(f"JSON.stringify(PACKMAP['{pid}'])"))
        check(mp[0] == 0 and mp[2] == 2 and mp[6] == 6 and mp[1] in (None, 1), f'the typo line costs only itself {mp[:8]}')
        sh = await pg.text_content('#sheet')
        check('عرفنا النشيد' in sh and 'عُرف' in sh, 'the parent sees what the pack recognised')
        await pg.click('#notPack'); await pg.wait_for_timeout(200)
        check(await pg.evaluate(f"!poemById('{pid}').pack && !BAYT['{pid}'] && !LESSON['{pid}'] && poemById('{pid}').noPack===true"), '«ليست هذه القصيدة» takes the pack back')
        await pg.evaluate("applyPacks()")
        check(await pg.evaluate(f"!poemById('{pid}').pack"), '…and it stays taken back')

        # ---- H3: a different patriotic poem with the pack's title is not the pack ----
        pid = await typed(pg, 'فلسطين داري', 'شاعر آخر', ['فلسطين يا أرض الجدود / سلام عليك', 'بلادي بلادي فداك / دمي وفؤادي',
                                                         'يا شعب قم للعلا / وارفع جبينك', 'مهد الجدود هنا / وهنا الأمل', 'فلسطين في القلب / لا تغيب'])
        check(await pg.evaluate(f"!poemById('{pid}').pack"), 'a title and a few common words are not enough')

        # ---- M6: pack word meanings, however the parent spells them ----
        W2 = PACKS['وصية لاجئ']
        pid = await typed(pg, 'وصية لاجئ', 'هاشم الرفاعي', [f"{' '.join(k)} سطر / تجريبي {i + 1}" for i, k in enumerate(W2['keys'])])
        await pg.evaluate(f"closeSheet(); openPoem('{pid}'); closeSheet()")
        w = next((x for x in W2['words'] if 'ى' in x), None)
        if w: check(await pg.evaluate(f"M('{w.replace('ى', 'ي')}',0)") == W2['words'][w], f'«{w}» typed with ي still has its meaning')

        # ---- M2/H2: a take of a memorised segment that is not due is practice, not a review ----
        await kid(pg, 'دلال', 10, 'g')
        await pg.evaluate("const s=st('٣'); s.z=6; s.mem=[0]; scheduleReview(s,0,1); saveS()")
        due = await pg.evaluate("reviewsDue('٣','دلال')")
        check(due == [], 'just memorised: no review due today')
        # the same rule the save sheet uses
        r = json.loads(await pg.evaluate("JSON.stringify((()=>{ const p=poemById('٣'), g=segOf(p,'دلال',0,6), s=KS('دلال')['٣']; return [g, (s.mem||[]).includes(g) && reviewsDue('٣','دلال').includes(g)]; })())"))
        check(r == [0, False], f'a take on the day of memorising is not counted as a review {r}')
        # H3: a review take the parent never heard brings the review back after three days
        await pg.evaluate("const s=st('٣'); s.rev={0:{step:1,due:Date.now()-1}}; s.rpend=[0]; s.rpendAt={0:Date.now()}; saveS()")
        check(await pg.evaluate("reviewsDue('٣','دلال')") == [], 'a review waiting for the parent is not asked again at once')
        await pg.evaluate("st('٣').rpendAt={0:Date.now()-4*864e5}; saveS()")
        check(await pg.evaluate("reviewsDue('٣','دلال')") == [0], '…but after three days unheard, the child reviews again')

        # ---- H4: echo mastery comes back for review ----
        await pg.evaluate("setKid('كريم'); closeSheet()")
        rid = await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'كريم', 'seg': 0, 'range': [0, 4], 'echo': True, 'lvl': 1})
        await pg.evaluate(f"stampEffects({{id:{json.dumps(rid)},poem:'٣٠',who:'كريم',seg:0,range:[0,4],echo:true}},'eok')")
        r = json.loads(await pg.evaluate("JSON.stringify(st('٣٠').rev||{})"))
        check('0' in r and r['0']['step'] == 0, f'«أتقنه» schedules an echo review for tomorrow {r}')

        # ---- ⭐ from one segment, not from two ----
        await pg.evaluate("setKid('كريم'); closeSheet(); openPoem('٣'); closeSheet()")
        await pg.evaluate("const s=st('٣'); s.qzs={0:{meaning:100}}; s.star=0; saveS(); seg=1; qType='complete'; qCounts=true; qRes=[{cnt:1,ok:1},{cnt:1,ok:1},{cnt:1,ok:1}]; qs=[1,2,3]; score=3; finishQuiz()")
        check(await pg.evaluate("st('٣').star") == 0, 'two kinds passed on two different segments: no ⭐')
        await pg.evaluate("closeSheet(); seg=0; qType='complete'; qCounts=true; qRes=[{cnt:1,ok:1},{cnt:1,ok:1},{cnt:1,ok:1}]; qs=[1,2,3]; score=3; finishQuiz()")
        check(await pg.evaluate("st('٣').star") == 1, 'two kinds passed on the same segment: ⭐')

        # ---- M1: no echo while recording ----
        await pg.evaluate("closeSheet(); window.__r=rec; rec={state:'recording'}")
        await pg.evaluate("karaoke({id:'x'}, true)")
        check('أوقف التسجيل أولاً' in (await pg.text_content('#toast') or ''), 'echo refuses to start while recording')
        await pg.evaluate("rec=window.__r")

        # ---- backups: segment sizes travel, and progress in another size is not mixed in ----
        r = json.loads(await pg.evaluate("JSON.stringify(mergeStat({z:3,mem:[1],last:1},{z:4,mem:[2],last:2}))"))
        check(r['z'] == 3 and r['mem'] == [1], f'a backup counted in another segment size does not mix its segments in {r}')
        r = json.loads(await pg.evaluate("JSON.stringify(mergeStat({z:4,mem:[1],last:1},{z:4,mem:[2],qzs:{1:{order:90}},rpend:[1],rpendAt:{1:5},last:2}))"))
        check(sorted(r['mem']) == [1, 2] and r['qzs'] == {'1': {'order': 90}} and r['rpendAt'] == {'1': 5}, f'same size: merged {r}')

        # ---- names that are built-in properties are refused ----
        check(await pg.evaluate("okName('toString')===false && okName('valueOf')===false && okName('كريم')===true"), '«toString» cannot be a child\'s name')

        # ---- recordings from a backup keep only the fields the app knows ----
        r = json.loads(await pg.evaluate("JSON.stringify(cleanRec({poem:'٣',who:'كريم',when:1,dur:2,lvl:4,seg:0,range:[0,4],junk:'x'.repeat(50),b64:'',by:'أ. آية'}))"))
        check('junk' not in r and r['range'] == [0, 4] and r['by'] == 'أ. آية', f'unknown fields are dropped {sorted(r)}')

        # ---- the level of the poems apart from the age (a child who skipped a grade) ----
        await kid(pg, 'فرح', 8, 'b')
        check(await pg.evaluate("pathOf('فرح')[0]===pathOf('كريم')[0] || true") and await pg.evaluate("kidLevel('فرح')") == 8, 'level follows the age by default')
        await pg.evaluate("kidInfo['فرح'].lv=10; LS.set('kidInfo',kidInfo)")
        r = json.loads(await pg.evaluate("JSON.stringify([kidLevel('فرح'), segSize('فرح'), pathOf('فرح').slice(-3).join()===pathOf('دلال').slice(-3).join()])"))
        check(r == [10, 4, True], f'level 10: the older path and poems, segments still of an eight-year-old {r}')

        # ---- the day off: nothing is asked ----
        await pg.evaluate("const s=st('٣','دلال'); s.rev={0:{step:1,due:Date.now()-1}}; s.rpend=[]; saveS()")
        check(await pg.evaluate("reviewsDue('٣','دلال')") == [0], 'a review is due')
        await pg.evaluate("LS.set('restDay', new Date().getDay())")
        check(await pg.evaluate("reviewsDue('٣','دلال')") == [], '…and on the family\'s day off it is not asked')
        await pg.evaluate("LS.set('restDay',-1)")

        # ---- the whole poem memorised: it is reviewed whole; up to eight, the first review is tomorrow ----
        await pg.evaluate("setKid('كريم'); closeSheet()")
        rid = await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'كريم', 'seg': 0, 'range': [0, 3], 'memCand': True})
        await pg.evaluate(f"stampEffects({{id:{json.dumps(rid)},poem:'٣٠',who:'كريم',seg:0,range:[0,3],memCand:true}},'ok')")
        check(await pg.evaluate("st('٣٠','كريم').rev[0].due") == await pg.evaluate("dueIn(1)"), '«✓ حفظه» at seven: the first review tomorrow')
        n = await pg.evaluate("segments(poemById('٣٠'),'كريم').length")
        rid = await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'كريم', 'seg': n, 'range': [0, 10], 'memCand': True})
        await pg.evaluate(f"stampEffects({{id:{json.dumps(rid)},poem:'٣٠',who:'كريم',seg:{n},range:[0,10],memCand:true}},'ok')")
        r = json.loads(await pg.evaluate("JSON.stringify(Object.keys(st('٣٠','كريم').rev||{}))"))
        check(r == [str(n)], f'after the whole poem, only the whole is reviewed {r}')

        # ---- quizzes: a girl reads them as a girl; easy ordering is practice above eight; «أكمل البيت» keeps a line of the poem ----
        await pg.evaluate("setKid('دلال'); closeSheet(); openPoem('٣'); closeSheet()")
        check(await pg.evaluate("QTL('complete')") == '✍️ أكملي البيت' and await pg.evaluate("QTL('listen')") == '🔊 اسمعي واختاري', 'quiz names for a girl')
        check(await pg.evaluate("qEasy=true; typeCounts('order')") is False and await pg.evaluate("qEasy=false; typeCounts('order')") is True, 'easy ordering does not count at ten')
        ok = await pg.evaluate("""() => { let n=0, good=0; const mine=new Set(cur.verses.map(v=>v[1]));
          for(let t=0;t<40;t++){ qEasy=false; mode='quiz'; startQuiz('complete');
            const opts=[...document.querySelectorAll('#quizBox .opt')].map(b=>b.textContent); if(!opts.length) continue; n++; const right=cur.verses[qs[0]][1];
            if(opts.filter(o=>o!==right).some(o=>mine.has(o))) good++; } return [n,good]; }""")
        check(ok[0] > 0 and ok[0] == ok[1], f'every counted «أكمل البيت» has a wrong ending from the same poem {ok}')

        # ---- the adults: a PIN, and the teacher's changing code ----
        await pg.evaluate("closeSheet(); gateUntil=0; adults=[]; const a={role:'parent',name:'بابا',salt:'s1'}; a.pin=pinOf('2468',a.salt); adults.push(a); saveAdults()")
        await pg.evaluate("(()=>{ parentGate().then(v=>window.__g=v); })()"); await pg.wait_for_timeout(100)
        check(await pg.locator('#gPin').count() == 1 and 'اضغط' not in await pg.text_content('#sheet'), 'with a PIN, the gate asks for it and does not tell how to open it')
        await pg.fill('#gPin', '1111'); await pg.click('#gOk'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("Date.now()<gateUntil") is False, 'a wrong PIN does not open')
        await pg.fill('#gPin', '2468'); await pg.click('#gOk'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("window.__g===true && actor && actor.name==='بابا'"), 'the right PIN opens, and the adult is known')
        await pg.evaluate("adults.push({role:'teacher',name:'أ. آية',secret:'00112233445566778899aabb'}); saveAdults(); window.__f=null; shareFiles=async(items)=>{ window.__f=await items[0].blob.text(); }; teacherFile(teachers()[0])")
        await pg.wait_for_timeout(200)
        page = await pg.evaluate("window.__f")
        code = await pg.evaluate("tCode('00112233445566778899aabb', Math.floor(Date.now()/60000))")
        check(page and 'أ. آية' in page and 'sha256' in page and len(code) == 4, 'the teacher\'s file shows her changing code')
        await pg.evaluate("closeSheet(); teacherSession()"); await pg.fill('#tCode', '0000' if code != '0000' else '1111'); await pg.click('#tGo')
        check(not await pg.evaluate("tLive()"), 'a wrong code starts no session')
        await pg.fill('#tCode', code); await pg.click('#tGo'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("tLive() && tSess.name==='أ. آية'") and await pg.is_visible('#tBar'), 'the right code starts the session')
        await pg.evaluate("setKid('دلال'); closeSheet()")
        rid = await pg.evaluate(PUT, {'poem': '٦', 'who': 'دلال', 'seg': 0, 'range': [0, 6], 'memCand': True})
        await pg.evaluate(f"judgeNow({{id:{json.dumps(rid)},poem:'٦',title:'x',who:'دلال',seg:0,range:[0,6],memCand:true}})"); await pg.wait_for_timeout(100)
        check('ما حكمكِ' in await pg.text_content('#sheet'), 'in a session, the teacher judges a take as soon as it is saved')
        await pg.click('#sheet [data-st="ok"]'); await pg.wait_for_timeout(200)
        check(await pg.evaluate("st('٦','دلال').mem.length") == 0 and 'ما حكمكِ' in await pg.text_content('#sheet'), 'without the teacher\'s code of the minute, the child cannot stamp')
        await pg.fill('#jCode', await pg.evaluate("tCode('00112233445566778899aabb', Math.floor(Date.now()/60000))"))
        await pg.click('#sheet [data-st="ok"]'); await pg.wait_for_timeout(300)
        r = json.loads(await pg.evaluate(f"recMeta().then(a=>JSON.stringify(a.find(x=>x.id==={json.dumps(rid)})))"))
        check(r.get('stamp') == 'ok' and r.get('by') == 'أ. آية' and 0 in json.loads(await pg.evaluate("JSON.stringify(st('٦','دلال').mem)")), f'the stamp carries her name {r.get("stamp")} {r.get("by")}')
        news = json.loads(await pg.evaluate("JSON.stringify(LS.get('news',{})['دلال']||[])"))
        check(any(x.get('by') == 'أ. آية' for x in news), 'the child\'s news says who stamped')

        # ---- a teacher's PIN does not lock the parent out; a forgotten PIN has a recovery code ----
        await pg.evaluate("closeSheet(); gateUntil=0; tSess=null; adults=[{role:'teacher',name:'م',salt:'x',pin:pinOf('1357','x'),secret:'aa'}]; saveAdults(); (()=>{ parentGate(); })()"); await pg.wait_for_timeout(100)
        check(await pg.locator('#gateBtn').count() == 1, 'the parent without a PIN still has the long press when a teacher has one')
        await pg.evaluate("closeSheet(); window.__f=null; const a={role:'parent',name:'بابا',salt:'s2'}; a.pin=pinOf('2468',a.salt); a.rc=pinOf('ABCD1234',a.salt); adults.push(a); saveAdults(); (()=>{ parentGate().then(v=>window.__g2=v); })()"); await pg.wait_for_timeout(100)
        await pg.click('#gForgot'); await pg.fill('#gRc', 'abcd-1234'); await pg.click('#gRcOk'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("window.__g2===true") and await pg.locator('#pp1').count() == 1, 'the recovery code opens the page and asks for a new PIN')
        await pg.evaluate("closeSheet(); gateUntil=0")
        for _ in range(5):
            await pg.evaluate("(()=>{ parentGate(); })()"); await pg.wait_for_timeout(50); await pg.fill('#gPin', '0000'); await pg.click('#gOk'); await pg.evaluate("closeSheet()")
        await pg.evaluate("(()=>{ parentGate(); })()"); await pg.wait_for_timeout(50); await pg.fill('#gPin', '2468'); await pg.click('#gOk'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("Date.now()<gateUntil") is False, 'after five wrong tries, even the right PIN waits a minute')
        await pg.evaluate("closeSheet(); gateLockUntil=0; gateUntil=Date.now()+6e5")

        # ---- «نصوصي»: the typed poems go to a file and come back without typing ----
        await pg.evaluate("closeSheet(); window.__f=null; $('#txExport').click()"); await pg.wait_for_timeout(200)
        tx = await pg.evaluate("window.__f")
        o = json.loads(tx)
        check(o['kind'] == 'texts' and len(o['poems']) == await pg.evaluate("added.length"), f'«نصوصي» holds the typed poems ({len(o["poems"])})')
        import tempfile, os
        f = os.path.join(tempfile.mkdtemp(), 'نصوصي.json'); open(f, 'w', encoding='utf-8').write(tx)
        await pg.evaluate("added.length=0; LS.set('added',added); gateUntil=Date.now()+6e5")
        await pg.set_input_files('#txImport', f); await pg.wait_for_timeout(400)
        check(await pg.evaluate("added.length") == len(o['poems']) and await pg.evaluate("added.some(p=>p.pack==='وصية لاجئ')"), 'imported again: the poems and their packs are back')
        await pg.set_input_files('#txImport', f); await pg.wait_for_timeout(400)
        check(await pg.evaluate("added.length") == len(o['poems']), 'importing the same file twice adds nothing')

        # ---- the service worker keeps pictures across versions ----
        sw = open('www/sw.js', encoding='utf-8').read()
        check("IMG='anasheed-img'" in sw and "mode==='navigate'" in sw, 'pictures live in a lasting cache; the page fallback is for pages only')

        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print(f'\n{len(fails)} failures'); sys.exit(1 if fails else 0)

asyncio.run(main())
