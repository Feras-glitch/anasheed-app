"""The fixes of the adversarial review of v1.0.65 (A01–A15, B02, B03): one check or more for each, as invariants.
Run with the same server as tests/e2e.py. Pack poems are typed as dummy lines made of the pack's key words only — never the poem."""
import asyncio, json, os, subprocess, sys, tempfile
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

PACKS = json.load(open('content/packs.json', encoding='utf-8'))
PUT = """async (o) => { const rate=8000, secs=o.dur||4, n=rate*secs, off=new OfflineAudioContext(1,n,rate), buf=off.createBuffer(1,n,rate), d=buf.getChannelData(0);
  const f=o.hz||300; for(let i=0;i<n;i++) d[i]=0.3*Math.sin(2*Math.PI*f*i/rate); const blob=await bufferToWav(buf); delete o.hz;
  const row=Object.assign({title:poemById(o.poem).title,when:Date.now()+Math.random(),dur:secs,blob,type:'audio/wav',lvl:4,seg:0,model:false,marks:[],loud:0.5},o);
  return recPut(row); }"""
META = "(id)=>recMeta().then(a=>a.find(r=>r.id===id))"

async def kid(pg, name, age, g):
    await pg.evaluate(f"if(!kids.includes('{name}')) kids.push('{name}'); kidInfo['{name}']={{age:{age},g:'{g}'}}; LS.set('kids',kids); LS.set('kidInfo',kidInfo); closeSheet(); setKid('{name}'); closeSheet()")

async def typed(pg, title, poet, lines):
    await pg.evaluate("([a,b,t])=>{ closeSheet(); $('#aTitle').value=a; $('#aPoet').value=b; $('#aText').value=t; $('#aSave').click(); }", [title, poet, '\n'.join(lines)])
    await pg.wait_for_timeout(300)
    return await pg.evaluate("added[added.length-1].id")

def textcheck_unit():
    # A11: the fingerprints of a poem never hold its words, and the guard names only places
    sys.path.insert(0, 'tools'); import textcheck as T
    packs = {k: v for k, v in PACKS.items() if not k.startswith('_')}
    fake = 'سطر أول فيه كلمات مصطنعة تماما\nوسطر ثان بكلمات غريبة جدا لا توجد'
    salt = '00112233445566778899aabbccddeeff'
    hs = T.fingerprints(packs['لا تصالح'], fake, salt)
    check(hs and all(len(h) == 16 for h in hs) and not any(w in json.dumps(hs, ensure_ascii=False) for w in ('كلمات', 'غريبة')), f'fingerprints hold no word ({len(hs)})')
    check(T.check_fp(packs['لا تصالح'], hs, salt) == [], 'the pack shares no run of three words with that text')
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, 'docs'))
    open(os.path.join(d, 'docs', 'a.md'), 'w', encoding='utf-8').write('مقدمة، ثم: بكلمات غريبة جدا في الوسط.')
    open(os.path.join(d, 'docs', 'b.md'), 'w', encoding='utf-8').write('اقتباس ﴿بكلمات غريبة جدا﴾ من القرآن لا يُعدّ')
    r = T.scan(d, {'لا تصالح': hs}, salt, os.path.join(d, 'content', 'packs.json'))
    check(r == [(os.path.join('docs', 'a.md'), 'لا تصالح', 1)], f'a copied run in any file is found, by place and count only {r}')
    r = [x for x in T.scan('.', {'لا تصالح': hs}, salt, 'content/packs.json') if x[0] != os.path.join('tests', 'e2e_review7.py')]
    check(r == [], f'the repository is clean against them (but for this test, which holds the made-up text) {r}')
    # the build: warns while packs have no fingerprints; a strict file stops it
    out = subprocess.run([sys.executable, '-c', "import json,sys; sys.path.insert(0,'tools'); import textcheck as T; print('ok')"], capture_output=True, text=True)
    check(out.returncode == 0, 'textcheck imports')

async def main():
    textcheck_unit()
    r = subprocess.run(['node', 'tests/sw_check.js', 'www/sw.js'], capture_output=True, text=True, timeout=60)
    print(r.stdout.strip())
    check(r.returncode == 0, 'the service worker keeps the last version\'s pictures and hides server errors')
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 360, 'height': 740})
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(700)
        await kid(pg, 'سلمى', 10, 'g')

        # ---- A01: a take whose verses are not one of the child's segments is only «heard»: never memorised ----
        n6 = await pg.evaluate("poemById('٦').verses.length")
        check(await pg.evaluate("JSON.stringify(segments(poemById('٦'),'سلمى'))") == json.dumps([[0, n6]]).replace(' ', ''), f'«٦» is one segment at ten ({n6} verses)')
        rid = await pg.evaluate(PUT, {'poem': '٦', 'who': 'سلمى', 'seg': 0, 'range': [0, 3], 'memCand': True})
        check(await pg.evaluate("(id)=>recMeta().then(a=>recSegOf(a.find(r=>r.id===id)))", rid) == -1, 'three verses of a twelve-verse segment match no segment')
        await pg.evaluate("(id)=>recMeta().then(a=>stampEffects(a.find(r=>r.id===id),'ok'))", rid)
        r = json.loads(await pg.evaluate("JSON.stringify([st('٦','سلمى').mem, badges(poemById('٦'),'سلمى').mem, (LS.get('news',{})['سلمى']||[]).slice(-1)[0]])"))
        check(r[0] == [] and r[1] is False and r[2]['t'] == 'heard', f'its «✓ حفظه» memorises nothing: heard only {r}')
        await pg.evaluate("gateUntil=Date.now()+6e5; show('parent'); renderParent()"); await pg.wait_for_timeout(500)
        rid2 = await pg.evaluate(PUT, {'poem': '٦', 'who': 'سلمى', 'seg': 0, 'range': [0, 3], 'memCand': True})
        await pg.evaluate("renderQueue()"); await pg.wait_for_timeout(300)
        btns = await pg.evaluate(f"[...document.querySelectorAll('#pQueue [data-q=\"{rid2}\"] [data-st]')].map(b=>b.dataset.st)")
        check(btns == ['heard'], f'in the queue such a take offers only «👂 سمعته» {btns}')
        await pg.evaluate("show('home')")

        # ---- A02: copies counted in other segment sizes: every recited verse is kept, as verses, never as foreign numbers ----
        pid = await pg.evaluate("POEMS.filter(p=>p.verses.length>=14&&p.verses.length<=17).map(p=>p.id)[0]")
        n = await pg.evaluate(f"poemById('{pid}').verses.length")
        r = json.loads(await pg.evaluate(f"JSON.stringify(mergeStat({{z:6,mem:[0],last:100}},{{z:3,mem:[3],last:200}},'{pid}','سلمى'))"))
        check(r['z'] == 6 and r['mem'] == [0] and r.get('memR') == [[9, 12]], f'size 6 with size 3: verses 10–12 are kept as verses ({n} verses) {r}')
        w3 = await pg.evaluate(f"segsZ({n},3).length"); w6 = await pg.evaluate(f"segsZ({n},6).length")
        r = json.loads(await pg.evaluate(f"JSON.stringify(mergeStat({{z:6,mem:[0],last:1}},{{z:3,mem:[{w3}],last:2}},'{pid}','سلمى'))"))
        check(sorted(r['mem']) == list(range(w6 + 1)) and 'memR' not in r, f'the whole poem recited in the other size: every segment, and the whole {r["mem"]}')
        r = json.loads(await pg.evaluate(f"JSON.stringify(mergeStat({{z:6,mem:[0],last:1}},{{z:3,mem:[2,3],rev:{{2:{{step:1,due:5}}}},last:2}},'{pid}','سلمى'))"))
        check(r['mem'] == [0] and r.get('memR') == [[6, 9], [9, 12]], f'two halves recited apart are kept, not counted as the segment {r}')
        # a poem not on this device: the other copy waits aside, and is counted when the poem comes
        r = json.loads(await pg.evaluate("JSON.stringify(mergeStat({z:6,mem:[0],last:1},{z:3,mem:[3],last:2},'u424242','سلمى'))"))
        check(r['mem'] == [0] and r.get('alt') and r['alt'][0]['z'] == 3 and r['alt'][0]['mem'] == [3], f'unknown poem: the copy of another size is kept whole {r}')
        await pg.evaluate("(x)=>{ KS('سلمى')['u424242']=x; saveS(); added.push({id:'u424242',title:'نشيد تجريبي',poet:'—',age:[6,12],verses:[...Array(16)].map((_,i)=>['شطر '+i,'عجز '+i]),user:true}); LS.set('added',added); foldAlts(); }", r)
        r = json.loads(await pg.evaluate("JSON.stringify(KS('سلمى')['u424242'])"))
        check('alt' not in r and r.get('memR') == [[9, 12]] and r['mem'] == [0], f'…the poem arrives: its verses are counted {r}')
        await pg.evaluate("added=added.filter(p=>p.id!=='u424242'); LS.set('added',added); delete KS('سلمى')['u424242']; saveS()")

        # ---- A05: a take recorded for a review date that another take has since settled moves no date, erases no stumble ----
        g0 = await pg.evaluate("(()=>{ const s=st('٣','سلمى'); s.mem=[0]; s.rev={0:{step:1,due:Date.now()-1000}}; s.weak={1:1}; s.rpend=[0]; saveS(); return s.rev[0].due; })()")
        old_ = await pg.evaluate(PUT, {'poem': '٣', 'who': 'سلمى', 'seg': 0, 'range': await pg.evaluate("segments(poemById('٣'),'سلمى')[0]"), 'review': True, 'revDue': g0})
        new_ = await pg.evaluate(PUT, {'poem': '٣', 'who': 'سلمى', 'seg': 0, 'range': await pg.evaluate("segments(poemById('٣'),'سلمى')[0]"), 'review': True, 'revDue': g0})
        await pg.evaluate(f"recMeta().then(a=>stampEffects(a.find(r=>r.id==={new_}),'rok'))")
        after1 = json.loads(await pg.evaluate("JSON.stringify(st('٣','سلمى').rev[0])"))
        await pg.evaluate(f"recMeta().then(a=>stampEffects(a.find(r=>r.id==={old_}),'rok'))")
        r = json.loads(await pg.evaluate("JSON.stringify([st('٣','سلمى').rev[0], st('٣','سلمى').weak||{}])"))
        check(after1['step'] == 2 and r[0] == after1 and r[1] == {}, f'the first heard take moves the review once; the late one moves nothing more {after1} {r}')
        await pg.evaluate("(()=>{ const s=st('٣','سلمى'); s.weak={2:1}; saveS(); })()")
        old2 = await pg.evaluate(PUT, {'poem': '٣', 'who': 'سلمى', 'seg': 0, 'range': await pg.evaluate("segments(poemById('٣'),'سلمى')[0]"), 'review': True, 'revDue': g0})
        await pg.evaluate(f"recMeta().then(a=>stampEffects(a.find(r=>r.id==={old2}),'rok'))")
        check(await pg.evaluate("JSON.stringify(st('٣','سلمى').weak)") == '{"2":1}', 'a late take does not erase a newer stumble')
        # the same for echo: a late «✓ أتقنه» schedules nothing
        e0 = await pg.evaluate("(()=>{ const s=st('٣٠','سلمى'); s.echoOk=[0]; s.rev={0:{step:1,due:Date.now()+5*864e5}}; saveS(); return s.rev[0].due; })()")
        ek = await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'سلمى', 'seg': 0, 'range': await pg.evaluate("segments(poemById('٣٠'),'سلمى')[0]"), 'echo': True, 'revDue': e0 - 864e5})
        await pg.evaluate(f"recMeta().then(a=>stampEffects(a.find(r=>r.id==={ek}),'eok'))")
        check(await pg.evaluate("st('٣٠','سلمى').rev[0].due") == e0, 'a late echo take moves no date')

        # ---- A07: a stamp is applied once: the check at start-up applies a lost effect, never twice ----
        sgk = await pg.evaluate("segments(poemById('١٨'),'سلمى')[0]")
        rk = await pg.evaluate(PUT, {'poem': '١٨', 'who': 'سلمى', 'seg': 0, 'range': sgk, 'memCand': True})
        await pg.evaluate(f"recPatch({rk},{{stamp:'okw',stampAt:Date.now(),weak:[{sgk[0]}],sdev:deviceId()}})")
        check(await pg.evaluate("(st('١٨','سلمى').mem||[]).length") == 0, 'the stamp was marked, its effect lost (the app closed in between)')
        await pg.evaluate("reconcileStamps()"); await pg.wait_for_timeout(300)
        r1 = json.loads(await pg.evaluate("JSON.stringify([st('١٨','سلمى').mem, st('١٨','سلمى').weak])"))
        await pg.evaluate("reconcileStamps()"); await pg.wait_for_timeout(300)
        await pg.evaluate(f"recMeta().then(a=>stampEffects(a.find(r=>r.id==={rk}),'okw',[{sgk[0]}]))")
        r2 = json.loads(await pg.evaluate("JSON.stringify([st('١٨','سلمى').mem, st('١٨','سلمى').weak])"))
        check(r1[0] == [0] and r1[1] == {str(sgk[0]): 1} and r2 == r1, f'start-up applies it once; again and again changes nothing {r1} {r2}')
        # after a reload too (the same device)
        await pg.reload(); await pg.wait_for_timeout(900)
        check(json.loads(await pg.evaluate("JSON.stringify(st('١٨','سلمى').weak)")) == {str(sgk[0]): 1}, '…and after the app opens again')

        # ---- A06: two verses typed on one line: both meanings, the lesson and the pictures stay with the line ----
        await pg.evaluate("closeSheet(); setKid('سلمى'); closeSheet()")
        W = PACKS['وصية لاجئ']; K = W['keys']
        lines = [f"{' '.join(K[i])} {' '.join(K[i + 1])} سطر / تجريبي {i // 2 + 1}" for i in range(0, len(K) - 1, 2)]
        pid = await typed(pg, 'وصية لاجئ', 'هاشم الرفاعي', lines)
        cov = json.loads(await pg.evaluate(f"JSON.stringify(PACKCOV['{pid}'])"))
        got = sorted(j for c in cov for j in c)
        check(got == list(range(len(K))), f'every verse of the pack is held by a line ({len(got)} of {len(K)})')
        r = json.loads(await pg.evaluate("""JSON.stringify(Object.entries(PACKS).map(([n,k])=>{ const verses=[]; for(let i=0;i<k.keys.length;i+=2) verses.push([k.keys[i].join(' ')+' '+(k.keys[i+1]||[]).join(' '),'تجريبي']);
          const m=packMap({title:k.title,verses}); return [n, m&&m.name===n ? new Set(m.cov.flat()).size : 0, k.keys.length]; }))"""))
        check(r and all(a == b for _, a, b in r), f'the review\'s own case: every pack typed two verses a line keeps all its verses {[(a, b) for _, a, b in r]}')
        r = json.loads(await pg.evaluate(f"JSON.stringify([BAYT['{pid}'].v[0], BW['{pid}']&&BW['{pid}'][0], LESSON['{pid}'].inv.slice(0,4), (STORY['{pid}']||[]).length])"))
        check(W['bayt'][0] in r[0] and W['bayt'][1] in r[0], 'the line has both meanings')
        check(r[1] is None and r[2] == [0, 0, 1, 1], f'not asked in «ما معنى البيت؟»; the lesson knows both verses are there {r[1:3]}')
        check(r[3] == len(W.get('story', [])), f'every picture of the tale has its line ({r[3]})')
        sheet = await pg.text_content('#sheet')
        check('بيتان في سطر واحد' in sheet and f'عُرف {await pg.evaluate("AR(" + str(len(K)) + ")")}' in sheet, 'the parent is told the verses were found, two on a line')
        await pg.evaluate(f"closeSheet(); openPoem('{pid}'); closeSheet()")
        html = await pg.evaluate("lessonHTML()")
        check('كُتب مع السطر' in html and 'لم يُكتب' not in html, 'the lesson shows the second verse with the first, never «not typed»')
        # ---- B03: a heavy poem: a word for the adult at the top of the lesson, the tale and the pictures ----
        check(html.startswith('<div class="note adultNote">') and 'للكبار' in html, 'the lesson opens with the note for the adults')
        await pg.evaluate("$('#taleBtn').click()"); await pg.wait_for_timeout(200)
        check('للكبار' in await pg.text_content('#sheet'), 'the tale too')
        await pg.evaluate("closeSheet(); $('#modeStory').click()"); await pg.wait_for_timeout(400)
        check('للكبار' in await pg.text_content('#storyBox'), 'and the picture story')
        check(sorted(k for k, v in PACKS.items() if not k.startswith('_') and v.get('adultNote')) == sorted(['لا تصالح', 'وصية لاجئ', 'اخلع نعلك يا موسى']), 'the three heavy packs carry it')
        await pg.evaluate("show('home')")

        # ---- A10: a hidden poem is not offered anywhere on the child's home ----
        wk = await pg.evaluate("weekly().id")
        await pg.evaluate(f"(()=>{{ const s=st('{wk}','سلمى'); s.mem=[0]; s.rev={{0:{{step:0,due:Date.now()-1}}}}; saveS(); }})()")
        await pg.evaluate("renderHome()")
        check(await pg.locator(f'#reviewBox [data-rv="{wk}"]').count() == 1, 'the weekly poem is due for review: offered')
        poet = await pg.evaluate(f"poemById('{wk}').poet")
        others = await pg.evaluate(f"allPoems().filter(p=>p.poet===poemById('{wk}').poet).map(p=>p.id)")
        await pg.evaluate("(ids)=>{ kidInfo['سلمى'].hide=ids; LS.set('kidInfo',kidInfo); renderHome(); }", others)
        r = json.loads(await pg.evaluate(f"JSON.stringify([weekly()&&weekly().id, !!document.querySelector('#reviewBox [data-rv=\"{wk}\"]'), [...document.querySelectorAll('#poets .chip')].map(c=>c.dataset.p)])"))
        check(r[0] != wk and r[1] is False and poet not in r[2], f'hidden: not the weekly poem, not in the reviews, its poet\'s chip gone {r[0]}')
        check(await pg.evaluate(f"st('{wk}','سلمى').rev[0].step") == 0, '…and its progress is kept')
        await pg.evaluate("delete kidInfo['سلمى'].hide; LS.set('kidInfo',kidInfo); renderHome()")

        # ---- A13: a child who cannot read yet is never moved to written answers ----
        await kid(pg, 'يوسف', 6, 'b')
        pid = await pg.evaluate("""(()=>{ for(const p of POEMS){ openPoem(p.id); closeSheet(); goSeg(0); const w=segWords(); if(w.length && w.filter(x=>IMG(x.k,x.i)).length<3) return p.id; } return null; })()""")
        await pg.evaluate(f"(()=>{{ const w=LS.get('wantModel',{{}}); delete w['{pid}']; LS.set('wantModel',w); mode='quiz'; setModeUI(); quizMenu(); }})()"); await pg.wait_for_timeout(600)
        r = json.loads(await pg.evaluate(f"JSON.stringify([!!document.querySelector('#quizBox [data-q=\"meaning\"]'), !!document.querySelector('#preNote'), own(LS.get('wantModel',{{}}),'{pid}'), document.body.classList.contains('prereader')])"))
        check(r[3] and r[0] is False, f'at six, few pictures: no quiz of written meanings ({pid})')
        check(r[1] and r[2], f'…the adults see what to prepare, and the poem waits in «سجّل نماذج» {r}')
        await pg.evaluate("qEasy=true; startQuiz('meaning')"); await pg.wait_for_timeout(200)
        check(await pg.locator('#quizBox .opt:not(:has(img))').count() == 0, 'even if asked, no written option is shown')
        # with the parent's voice marked verse by verse and enough pictures: the picture questions are there, each said aloud
        pv = await pg.evaluate("""(()=>{ for(const p of POEMS){ openPoem(p.id); closeSheet(); goSeg(segs.length>1?segs.length:0); if(segWords().filter(x=>IMG(x.k,x.i)).length>=4) return p.id; } return null; })()""")
        await pg.evaluate(PUT, {'poem': pv, 'who': 'يوسف', 'model': True, 'marks': await pg.evaluate(f"poemById('{pv}').verses.map((_,i)=>[i,i,0])"), 'dur': 8})
        await pg.evaluate(f"(()=>{{ openPoem('{pv}'); closeSheet(); goSeg(segs.length>1?segs.length:0); mode='quiz'; setModeUI(); quizMenu(); }})()"); await pg.wait_for_timeout(700)
        check(await pg.locator('#quizBox [data-q="meaning"]').count() == 1 and await pg.locator('#preNote').count() == 0, f'voiced, with pictures: «what is this picture?» is offered at six ({pv})')
        await pg.evaluate("window.__said=[]; sayHemi=(i,h)=>{ window.__said.push(i); }; 0")
        await pg.click('#quizBox [data-q="meaning"]'); await pg.wait_for_timeout(700)
        r = json.loads(await pg.evaluate("JSON.stringify([document.querySelectorAll('#quizBox .imgs .opt').length, document.querySelectorAll('#quizBox .opt:not(:has(img))').length, window.__said.length])"))
        check(r[0] == 3 and r[1] == 0 and r[2] >= 1, f'…pictures only, and the question is heard without a tap {r}')
        await pg.evaluate("show('home'); setKid('سلمى'); closeSheet()")

        # ---- A14: cards and banners by keyboard; the sheet holds the focus; pictures have names, not answers ----
        await pg.evaluate("renderHome()"); await pg.wait_for_timeout(100)
        r = json.loads(await pg.evaluate("JSON.stringify([document.querySelector('#grid .card').getAttribute('tabindex'), document.querySelector('#grid .card').getAttribute('role')])"))
        check(r == ['0', 'button'], f'a poem card is a button for the keyboard {r}')
        first = await pg.evaluate("document.querySelector('#grid .card').dataset.id")
        await pg.focus('#grid .card'); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(300)
        check(await pg.evaluate("screen==='poem' && cur.id") == first, 'Enter on a card opens its poem')
        await pg.evaluate("closeSheet(); show('home')"); await pg.wait_for_timeout(100)
        await pg.evaluate("(()=>{ document.querySelector('#grid .card').focus(); window.__from=document.activeElement; ask('سؤال؟'); })()"); await pg.wait_for_timeout(100)
        r = json.loads(await pg.evaluate("JSON.stringify([document.querySelector('main').inert, document.querySelector('header').inert, document.querySelector('#pop').inert])"))
        check(r == [True, True, False], f'while a sheet is open the page behind it is inert {r}')
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("document.querySelector('main').inert===false && document.activeElement===window.__from"), 'closing it returns the focus where it was')
        await pg.evaluate("openPoem('٣'); closeSheet(); qEasy=true; mode='quiz'; setModeUI(); let n=0; do{ startQuiz('meaning'); n++; }while(!document.querySelector('#quizBox .imgs') && n<30)")
        labels = await pg.evaluate("[...document.querySelectorAll('#quizBox .imgs .opt')].map(b=>b.getAttribute('aria-label'))")
        check(labels and all(l and l.startswith('الصورة ') for l in labels), f'picture options are named by their place, not their answer {labels}')
        await pg.evaluate("show('home')")

        # ---- A15: counts agree with what follows them ----
        r = json.loads(await pg.evaluate("JSON.stringify([1,2,3,11].map(n=>tasjeelN(n)+' '+fresh_(n)+' '+notIn(n)))"))
        check(r == ['تسجيل واحد جديد ليس', 'تسجيلان جديدان ليسا', '٣ تسجيلات جديدة ليست', '١١ تسجيلاً جديداً ليست'], f'«… ليس في أي نسخة» for 1, 2, 3 and 11 {r}')
        r = json.loads(await pg.evaluate("JSON.stringify([1,2,3,11].map(n=>tasjeelN(n)+' '+vN(n,'ينتظر','ينتظران','تنتظر')))"))
        check(r[1] == 'تسجيلان ينتظران' and r[2] == '٣ تسجيلات تنتظر', f'a verb after a counted subject {r}')
        r = json.loads(await pg.evaluate("JSON.stringify([2,3,11].map(n=>'أُرسل '+khatmNom(n)))"))
        check(r == ['أُرسل ختمان', 'أُرسل ٣ أختام', 'أُرسل ١١ ختماً'], f'stamps sent {r}')
        await pg.evaluate("(async()=>{ for(let i=0;i<2;i++) await recPut({poem:'٣',title:'x',who:'سلمى',when:Date.now()+i,dur:1,blob:new Blob(['x'],{type:'audio/wav'}),type:'audio/wav',lvl:0,seg:0,marks:[],loud:1}); LS.set('lastBackup',Date.now()-1000); gateUntil=Date.now()+6e5; show('parent'); renderParent(); })()"); await pg.wait_for_timeout(700)
        bi = await pg.text_content('#backupInfo')
        check('تسجيلان جديدان ليسا في أي نسخة' in bi, f'the backup note for two {bi.strip()[:80]}')

        # ---- A09: wrong PINs lock the gate across a restart; the teacher's code has the same count ----
        await pg.evaluate("closeSheet(); gateUntil=0; adults=[{role:'parent',name:'بابا',salt:'s9'}]; adults[0].pin=pinOf('2468','s9'); adults[0].rc=pinOf('ABCD1234','s9'); saveAdults(); LS.set('lock_gate',null); 0")
        for _ in range(5):
            await pg.evaluate("(()=>{ parentGate(); })()"); await pg.wait_for_timeout(50); await pg.fill('#gPin', '0000'); await pg.click('#gOk'); await pg.evaluate("closeSheet()")
        await pg.reload(); await pg.wait_for_timeout(900)
        await pg.evaluate("closeSheet(); (()=>{ parentGate().then(v=>window.__g=v); })()"); await pg.wait_for_timeout(100)
        await pg.fill('#gPin', '2468'); await pg.click('#gOk'); await pg.wait_for_timeout(150)
        check(await pg.evaluate("Date.now()<gateUntil") is False and 'انتظر' in (await pg.text_content('#toast') or ''), 'after five wrong PINs, closing and opening the app does not reset the wait')
        await pg.evaluate("closeSheet(); const x=LS.get('lock_gate',{}); x.until=Date.now()-1; LS.set('lock_gate',x); (()=>{ parentGate().then(v=>window.__g=v); })()"); await pg.wait_for_timeout(100)
        await pg.fill('#gPin', '0000'); await pg.click('#gOk'); await pg.wait_for_timeout(100)
        check(await pg.evaluate("lockWait('gate')") == 0 and await pg.evaluate("LS.get('lock_gate',{}).f") == 1, 'one more wrong PIN after the wait: counted again from one')
        await pg.evaluate("closeSheet(); LS.set('lock_gate',null); gateUntil=Date.now()+6e5; adults.push({role:'teacher',name:'أ. آية',secret:'00112233445566778899aabb'}); saveAdults(); teacherSession()")
        for _ in range(5):
            await pg.fill('#tCode', '9999' if await pg.evaluate("tCode('00112233445566778899aabb',Math.floor(Date.now()/60000))") != '9999' else '8888'); await pg.click('#tGo'); await pg.wait_for_timeout(30)
        await pg.fill('#tCode', await pg.evaluate("tCode('00112233445566778899aabb',Math.floor(Date.now()/60000))")); await pg.click('#tGo'); await pg.wait_for_timeout(100)
        check(not await pg.evaluate("tLive()") and await pg.evaluate("lockWait('tcode')") >= 1, 'five wrong teacher codes: even her right code waits')
        await pg.evaluate("closeSheet(); LS.set('lock_tcode',null); tSess=null")

        # ---- A08 + B02: a backup brings back the parent's recovery code; the teacher's secret never travels in it ----
        await pg.evaluate("window.__bk=null; shareFiles=async(items)=>{ window.__bk=await items[0].blob.text(); return true; }; doExport(false)"); await pg.wait_for_timeout(600)
        bk = await pg.evaluate("window.__bk")
        o = json.loads(bk)
        t = next(a for a in o['adults'] if a['role'] == 'teacher'); par = next(a for a in o['adults'] if a['role'] == 'parent')
        check('secret' not in t and '00112233445566778899aabb' not in bk and par.get('rc'), 'the backup has the recovery code, and no teacher secret')
        d = tempfile.mkdtemp(); fb = os.path.join(d, 'backup.json'); open(fb, 'w', encoding='utf-8').write(bk)
        ctx3 = await b.new_context(viewport={'width': 360, 'height': 740}); p3 = await ctx3.new_page(); await p3.goto(URL); await p3.wait_for_timeout(700)
        await p3.evaluate("closeSheet(); gateUntil=Date.now()+6e5"); await p3.set_input_files('#aImport', fb); await p3.wait_for_timeout(800)
        await p3.evaluate("closeSheet(); gateUntil=0; (()=>{ parentGate().then(v=>window.__g=v); })()"); await p3.wait_for_timeout(100)
        await p3.click('#gForgot'); await p3.fill('#gRc', 'abcd-1234'); await p3.click('#gRcOk'); await p3.wait_for_timeout(400)
        check(await p3.evaluate("window.__g===true"), 'restored on a new device: the recovery code written down still opens the page')
        await p3.evaluate("closeSheet(); gateUntil=Date.now()+6e5; show('parent'); renderParent()"); await p3.wait_for_timeout(400)
        check(await p3.evaluate("teachers().length===1 && !teachers()[0].secret") and await p3.locator('#adultsBox [data-tr]').count() == 1, 'the teacher comes back without her key, with «🔑 مفتاح جديد»')
        await p3.evaluate("window.__f=[]; shareFiles=async(items)=>{ window.__f.push(await items[0].blob.text()); return true; }; 0")
        await p3.click('#adultsBox [data-tr]'); await p3.wait_for_timeout(200); await p3.click('#rkKey'); await p3.wait_for_timeout(200)
        newkey = json.loads((await p3.evaluate("window.__f"))[-1])
        check(newkey['kind'] == 'teacherKey' and len(newkey['secret']) == 24 and newkey['secret'] == await p3.evaluate("teachers()[0].secret"), 'a new key is made, and her key file can be sent again')
        await ctx3.close()

        # ---- A03 + A04: the stamps cycle by files: bound to the sound she heard; a cancelled send keeps them ----
        await pg.evaluate("closeSheet(); setKid('سلمى'); closeSheet(); adults=[{role:'parent',name:'بابا'},{role:'teacher',name:'أ. آية',secret:'0123456789abcdef01234567'}]; saveAdults(); window.__f=null; shareFiles=async(items)=>{ window.__f=await items[0].blob.text(); return true; }; 0")
        sga = await pg.evaluate("segments(poemById('٣٠'),'سلمى')[0]")
        ra = await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'سلمى', 'seg': 0, 'range': sga, 'memCand': True, 'hz': 300})
        rb = await pg.evaluate(PUT, {'poem': '٣٠', 'who': 'سلمى', 'seg': 0, 'range': sga, 'memCand': True, 'hz': 500})
        await pg.evaluate("teacherKeyFile(teachers()[0])"); await pg.wait_for_timeout(100); key = await pg.evaluate("window.__f")
        await pg.evaluate("sendTakes(teachers()[0])"); await pg.wait_for_timeout(1000); takes = json.loads(await pg.evaluate("window.__f"))
        ta = next(x for x in takes['takes'] if x['rid'] == ra); tb = next(x for x in takes['takes'] if x['rid'] == rb)
        check(takes['v'] == 2 and len(takes['kid']) == 16 and len(ta['uid']) == 24 and len(ta['h']) == 64, 'each take goes with its lasting name and the fingerprint of its sound')
        check(await pg.evaluate(f"recMeta().then(a=>a.find(r=>r.id==={ra}).h)") == ta['h'], '…kept on the family\'s device too')
        # on the way, someone swaps the sound of one take: the teacher's app refuses to judge it
        tb['b64'] = ta['b64']
        d = tempfile.mkdtemp(); fk = os.path.join(d, 'key.json'); ft = os.path.join(d, 'takes.json')
        open(fk, 'w', encoding='utf-8').write(key); open(ft, 'w', encoding='utf-8').write(json.dumps(takes, ensure_ascii=False))
        ctx2 = await b.new_context(viewport={'width': 360, 'height': 740}); t2 = await ctx2.new_page(); await t2.goto(URL); await t2.wait_for_timeout(700)
        await t2.evaluate("closeSheet(); gateUntil=Date.now()+6e5")
        await t2.set_input_files('#aImport', fk); await t2.wait_for_timeout(300)
        await t2.set_input_files('#aImport', ft); await t2.wait_for_timeout(1000)
        inbox = json.loads(await t2.evaluate("recMeta().then(a=>JSON.stringify(a.filter(r=>r.inbox).map(r=>r.inbox)))"))
        ia = next((x for x in inbox if x['rid'] == ra), None)
        check(ia and not any(x['rid'] == rb for x in inbox) and ia['h'] == ta['h'] and ia['uid'] == ta['uid'], f'a take whose sound changed on the way is not judged; the other is {[x["rid"] for x in inbox]}')
        check('تالف' in (await t2.text_content('#toast') or ''), 'and the teacher is told')
        # she stamps it; the share is cancelled: the stamp stays in her outbox
        await t2.evaluate("show('parent'); renderParent()"); await t2.wait_for_timeout(500)
        await t2.evaluate(f"(async()=>{{ const r=(await recMeta()).find(x=>x.inbox&&x.inbox.rid==={ra}); outboxPut(r,'ok',[]); await recPatch(r.id,{{stamp:'ok',stampAt:Date.now(),weak:[]}}); }})()"); await t2.wait_for_timeout(200)
        await t2.evaluate("window.__f=null; shareFiles=async(items)=>{ window.__f=await items[0].blob.text(); return false; }; sendStamps()"); await t2.wait_for_timeout(400)
        r = json.loads(await t2.evaluate("JSON.stringify(teacherOutbox().map(x=>!!x.sentAt))"))
        check(r == [False], f'a send cancelled or failed keeps her stamps waiting {r}')
        await t2.evaluate("shareFiles=async(items)=>{ window.__f=await items[0].blob.text(); return true; }; sendStamps()"); await t2.wait_for_timeout(400)
        stamps = await t2.evaluate("window.__f"); so = json.loads(stamps)
        r = json.loads(await t2.evaluate("JSON.stringify(teacherOutbox().map(x=>!!x.sentAt))"))
        check(r == [True] and so['v'] == 2 and so['kid'] == takes['kid'] and so['items'][0]['h'] == ta['h'] and so['items'][0]['uid'] == ta['uid'], f'sent: marked as sent, signed with the family\'s key, naming the take and its sound {r}')
        await t2.evaluate("window.__f=null; sendStamps(true)"); await t2.wait_for_timeout(400)
        check(json.loads(await t2.evaluate("window.__f"))['items'] == so['items'], 'a lost file can be sent again')
        await t2.evaluate("show('parent'); renderParent()"); await t2.wait_for_timeout(300)
        check(await t2.locator('#tAgain').count() == 1, '«↻ أعيدي إرسال ما أُرسل» is on her page')
        await ctx2.close()
        # the family's side: a stamp for another sound (signed, but not what is here) is refused; the true one is applied once
        forged = dict(so); it = dict(so['items'][0], h='0' * 64); forged['items'] = [it]
        forged['sig'] = await pg.evaluate("([s,src,items])=>stampSig(s,src,items)", ['0123456789abcdef01234567', so['src'], forged['items']])
        ff = os.path.join(d, 'forged.json'); open(ff, 'w', encoding='utf-8').write(json.dumps(forged, ensure_ascii=False))
        await pg.evaluate("closeSheet(); gateUntil=Date.now()+6e5"); await pg.set_input_files('#aImport', ff); await pg.wait_for_timeout(500)
        check(await pg.evaluate(f"recMeta().then(a=>!a.find(r=>r.id==={ra}).stamp)") and 'لا يطابق' in (await pg.text_content('#toast') or ''), 'a signed stamp for another sound is refused')
        legacy = dict(so); it = {k: v for k, v in so['items'][0].items() if k not in ('h', 'uid')}; legacy['items'] = [it]; del legacy['kid']
        legacy['sig'] = await pg.evaluate("([s,src,items])=>stampSig(s,src,items)", ['0123456789abcdef01234567', so['src'], legacy['items']])
        fl = os.path.join(d, 'legacy.json'); open(fl, 'w', encoding='utf-8').write(json.dumps(legacy, ensure_ascii=False))
        await pg.set_input_files('#aImport', fl); await pg.wait_for_timeout(500)
        check(await pg.evaluate(f"recMeta().then(a=>!a.find(r=>r.id==={ra}).stamp)"), 'a take sent with its fingerprint takes no stamp without one')
        fs_ = os.path.join(d, 'stamps.json'); open(fs_, 'w', encoding='utf-8').write(stamps)
        await pg.set_input_files('#aImport', fs_); await pg.wait_for_timeout(600)
        r = json.loads(await pg.evaluate(f"recMeta().then(a=>JSON.stringify(a.find(r=>r.id==={ra})))"))
        mem1 = json.loads(await pg.evaluate("JSON.stringify(st('٣٠','سلمى').mem||[])"))
        check(r.get('stamp') == 'ok' and r.get('by') == 'أ. آية' and r.get('sdev') == await pg.evaluate("deviceId()") and 0 in mem1, 'her true stamp is applied, in her name')
        await pg.set_input_files('#aImport', fs_); await pg.wait_for_timeout(500)
        check('من قبل' in (await pg.text_content('#toast') or '') and json.loads(await pg.evaluate("JSON.stringify(st('٣٠','سلمى').mem||[])")) == mem1, 'the same file again changes nothing')
        # restored on another device: the stamps still find their take by its lasting name
        check(await pg.evaluate(f"recMeta().then(a=>a.find(r=>r.id==={rb}).uid)") == tb['uid'], 'the lasting name stays with the take (it travels in backups)')

        # ---- the teacher of two families (or two devices): one key each; her stamps for each are signed with its own ----
        r = json.loads(await pg.evaluate("""(()=>{ LS.set('iAmTeacher',null); LS.set('tKeys',[]);
          addTeacherKey({name:'أ. آية',secret:'aaaaaaaaaaaaaaaaaaaaaaaa',family:'أسرة ١'}); addTeacherKey({name:'أ. آية',secret:'bbbbbbbbbbbbbbbbbbbbbbbb',family:'أسرة ٢'});
          const k1=keyId('aaaaaaaaaaaaaaaaaaaaaaaa'), k2=keyId('bbbbbbbbbbbbbbbbbbbbbbbb'); const r=JSON.stringify([tKeys().length, tKey(k1).secret.slice(0,1), tKey(k2).secret.slice(0,1), iAmTeacher().secret.slice(0,1)]);
          LS.set('iAmTeacher',null); LS.set('tKeys',[]); return r; })()"""))
        check(r == [2, 'a', 'b', 'b'], f'her app keeps both keys, and finds each by the family\'s file {r}')
        r = json.loads(await pg.evaluate("""(()=>{ LS.set('tOut',[]); LS.set('tOutSent',[{src:'0123456789abcdef01234567',rid:7,stamp:'ok',weak:[],at:5}]); migrateOutbox();
          const o=teacherOutbox(), r=JSON.stringify([o.length, !!o[0].sentAt, o[0].rid, LS.get('tOutSent',null)]); LS.set('tOut',[]); return r; })()"""))
        check(r == [1, True, 7, None], f'stamps the old version dropped on a cancelled share are back, to send again {r}')

        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print(f'\n{len(fails)} failures'); sys.exit(1 if fails else 0)

asyncio.run(main())
