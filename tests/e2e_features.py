"""Checks for the round-3 features: age profile, level meter, verse marks, echo/karaoke,
family theater, certificate, easy quiz, conversation cards, parent model session, external pictures.
Run with the same server as tests/e2e.py."""
import asyncio, os, sys, tempfile, wave
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e import fake_voice

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

async def record_marked(pg, verses=3, step=1.6):
    """Record while pressing ⬇ at each verse, like a parent marking verses."""
    await pg.click('#recBtn'); await pg.wait_for_timeout(int(step * 1000))
    for _ in range(verses - 1):
        await pg.click('#nextV'); await pg.wait_for_timeout(int(step * 1000))
    await pg.click('#recBtn'); await pg.wait_for_timeout(600)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', f'--use-file-for-fake-audio-capture={fake_voice()}', '--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, permissions=['microphone'], accept_downloads=True)
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(600)

        # ---- age profile ----
        await pg.click('#kNew'); await pg.fill('#pIn', 'ليلى'); await pg.click('#pOk'); await pg.wait_for_timeout(200)
        check(await pg.locator('#sheet [data-a]').count() == 8, 'new child is asked for an age')
        await pg.click('#sheet [data-a="7"]'); await pg.wait_for_timeout(300)
        check(await pg.get_attribute('#ages .chip.on', 'data-age') == 'me' and all(a[0] <= 7 <= a[1] for a in await pg.evaluate("[...document.querySelectorAll('#grid .card')].map(c=>poemById(c.dataset.id).age)")), 'age 7 → only poems for age 7 shown by default')
        check(await pg.input_value('#speed') == '1', 'age 7 → slowest reading pace')
        await pg.evaluate('gateUntil=Date.now()+600000')  # the parent gate itself is tested in e2e.py

        # ---- pictures are separate files in the app build ----
        await pg.click('#grid .card[data-id="١"]'); await pg.wait_for_timeout(300)
        await pg.click('#verses .w.img >> nth=0'); await pg.wait_for_timeout(400)
        src = await pg.get_attribute('#sheet img', 'src'); nw = await pg.evaluate("document.querySelector('#sheet img').naturalWidth")
        check(src.startswith('img/') and nw > 100, f'word pictures load as files ({src})')
        await pg.click('#mClose')

        # ---- conversation card ----
        check(await pg.is_visible('#talkBtn'), 'fable shows «حديث مع والدك»')
        await pg.click('#talkBtn'); await pg.wait_for_timeout(150)
        check(await pg.locator('#sheet li').count() == 3, 'three discussion questions')
        await pg.click('#sheet button:has-text("تمام")')
        await pg.click('#modeStory'); await pg.wait_for_timeout(200)
        check(await pg.locator('#storyBox .talk li').count() == 3, 'questions appear at the end of the picture story')

        # ---- easy quiz: endings with a different rhyme ----
        await pg.click('#modeQuiz'); await pg.wait_for_timeout(100)
        check(await pg.get_attribute('#quizBox [data-e="1"]', 'class') == 'chip on', 'easy quiz is the default at age 7')
        await pg.click('#quizBox [data-q="complete"]'); await pg.wait_for_timeout(100)
        ok = await pg.evaluate("""(()=>{ const q=document.querySelector('#quizBox .q').textContent.split('…')[0].trim();
            const v=cur.verses.find(v=>q.startsWith(v[0].trim())); const right=v[1];
            const opts=[...document.querySelectorAll('#quizBox .opt')].map(b=>b.textContent);
            return opts.includes(right) && opts.filter(o=>o!==right).every(o=>rhymeOf(o)!==rhymeOf(right)); })()""")
        check(ok, 'easy distractors never share the poem\'s rhyme')
        await pg.click('#modeQuiz'); await pg.click('#quizBox [data-e="0"]'); await pg.click('#quizBox [data-q="order"]'); await pg.wait_for_timeout(100)
        n_reg = await pg.locator('#quizBox .opt').count()
        await pg.click('#modeQuiz'); await pg.click('#quizBox [data-e="1"]'); await pg.click('#quizBox [data-q="order"]'); await pg.wait_for_timeout(100)
        n_easy = await pg.locator('#quizBox .opt').count()
        check(n_reg == 4 and n_easy == 3, f'ordering: 3 verses when easy, 4 normally ({n_easy}/{n_reg})')

        # ---- level meter + verse marks while recording ----
        await pg.click('#modeSing'); await pg.wait_for_timeout(100)
        await pg.click('#recBtn'); await pg.wait_for_timeout(1200)
        check(await pg.evaluate("document.querySelector('#bar').classList.contains('recording')"), 'level meter shown while recording')
        w = await pg.evaluate("parseFloat(document.querySelector('#vu i').style.width)")
        check(w > 0, f'level meter moves with the voice ({w:.0f}%)')
        await pg.click('#nextV'); await pg.wait_for_timeout(1500); await pg.click('#nextV'); await pg.wait_for_timeout(1500)
        await pg.click('#recBtn'); await pg.wait_for_timeout(600)
        await pg.click('#keep'); await pg.wait_for_timeout(500); await pg.click('#sheet button:has-text("تمام")')
        marks = await pg.evaluate("recAll().then(a=>a[a.length-1].marks)")
        check(len(marks) == 3 and marks[0][0] == 0 and marks[2][0] == 2, f'verse marks saved with the recording {marks}')

        # ---- parent model session ----
        await pg.click('#back'); await pg.click('#goParent'); await pg.wait_for_timeout(400)
        await pg.fill('#parentName', 'بابا'); await pg.dispatch_event('#parentName', 'change')
        check(await pg.locator('#modelList .r').count() == 30, 'model list covers every poem')
        await pg.click('#modelList [data-m="١"]'); await pg.wait_for_timeout(400)
        check(await pg.locator('#modeBanner .modeBanner').count() == 1 and not await pg.is_checked('#autoOn'), 'model mode: banner, manual verse stepping')
        await record_marked(pg, verses=4)
        check(await pg.is_checked('#isModel') and await pg.input_value('#who') == 'بابا', 'model save sheet pre-filled')
        await pg.click('#keep'); await pg.wait_for_timeout(700)
        check(await pg.locator('#mnNext').count() == 1, 'after saving: go on to the next poem without a model')
        await pg.click('#mnStop'); await pg.wait_for_timeout(300)
        check(await pg.is_visible('#echoBtn'), '«ردّد بعدي» appears once a marked model exists')
        await pg.click('#modeStory'); await pg.wait_for_timeout(600)
        check(await pg.locator('#storyBox .splay:visible').count() >= 1, 'story pictures play their verses in the parent\'s voice')
        await pg.click('#modeSing')

        # ---- karaoke listen, then echo ----
        await pg.evaluate("window.__seen=new Set(); window.__iv=setInterval(()=>__seen.add(curLine),50)")
        await pg.click('#modelBtn'); await pg.wait_for_timeout(300)
        check(await pg.is_visible('#playBar'), 'listening plays verse by verse with a play bar')
        await pg.wait_for_timeout(6500)
        seen = set(await pg.evaluate("clearInterval(__iv), [...__seen]"))
        check(len(seen) >= 4 and 0 in seen, f'highlight follows the model across all verses {sorted(seen)}')
        if await pg.is_visible('#pbStop'): await pg.click('#pbStop')
        # a child of 10 gets the classic echo: the whole verse, then their turn
        await pg.evaluate("kidInfo['ليلى'].age=10")
        await pg.click('#echoBtn'); await pg.wait_for_timeout(300)
        turn = False
        for _ in range(20):
            if 'دورك' in (await pg.text_content('#pbText')): turn = True; break
            await pg.wait_for_timeout(250)
        check(turn, 'echo pauses for the child: «دورك! ردّد البيت»')
        l0 = await pg.evaluate('curLine'); await pg.click('#pbRepeat'); await pg.wait_for_timeout(500)
        check(await pg.evaluate('curLine') == l0 and 'استمع' in await pg.text_content('#pbText'), 'repeat replays the same verse')
        await pg.click('#pbStop'); await pg.wait_for_timeout(300)
        # a child of 7 gets the echo by half-verse, in three rounds, and the turns are recorded for the parent
        await pg.evaluate("kidInfo['ليلى'].age=7")
        n0 = await pg.evaluate('recMeta().then(a=>a.filter(r=>r.echo).length)')
        await pg.evaluate("window.__turns=[]; window.__prev=''; window.__iv2=setInterval(()=>{ const t=document.querySelector('#pbText').textContent; const turn=/دورك|أكمل|البيت كله/.test(t); if(turn && !/دورك|أكمل|البيت كله/.test(__prev)) __turns.push([curLine,t]); __prev=t; },40)")
        await pg.click('#echoBtn'); await pg.wait_for_timeout(9000)
        turns = await pg.evaluate("clearInterval(__iv2), __turns")
        check(len(turns) >= 2 and turns[0][0] == turns[1][0] if len(turns) >= 2 else False, f'young echo: two turns on the same verse (one per hemistich) {turns[:3]}')
        await pg.evaluate('stopPlay()'); await pg.wait_for_timeout(1500)
        check(await pg.evaluate('recMeta().then(a=>a.filter(r=>r.echo).length)') == n0 + 1, 'the child\'s echo turns are saved for the parent to hear')
        check(not await pg.is_visible('#playBar'), 'stop hides the play bar')

        # ---- ⭐ needs two kinds of quiz; the young hear a verse in the parent's voice and pick its picture ----
        await pg.click('#back'); await pg.click('#goParent'); await pg.wait_for_timeout(400)
        await pg.click('#modelList [data-m="٣٢"]'); await pg.wait_for_timeout(400)
        await record_marked(pg, verses=3)
        await pg.click('#keep'); await pg.wait_for_timeout(700); await pg.click('#mnStop'); await pg.wait_for_timeout(300)
        await pg.click('#modeQuiz'); await pg.wait_for_timeout(800)
        check(await pg.locator('#quizBox [data-q="listen"]').count() == 1, 'a young child with a verse-marked model is offered «اسمع واختر»')
        await pg.click('#quizBox [data-q="listen"]'); await pg.wait_for_timeout(1500)
        check(await pg.locator('#quizBox .imgs .opt').count() == 3 and await pg.is_visible('#lsPlay'), 'listening quiz: a 🔊 button and three pictures')
        nq = await pg.evaluate('qs.length')
        for _ in range(nq):
            await pg.click('#quizBox .opt[data-ok="1"]'); await pg.wait_for_timeout(1100)
        txt = await pg.text_content('#quizBox')
        check('نوع آخر' in txt and not await pg.evaluate('badges(cur).quiz'), 'one kind of quiz passed: the star waits for a second kind')
        await pg.click('#qMenu'); await pg.wait_for_timeout(300)
        check('✓' in await pg.text_content('#quizBox [data-q="listen"]'), 'the passed kind is ticked in the quiz menu')
        await pg.click('#quizBox [data-q="complete"]')
        nq = await pg.evaluate('qs.length')
        for _ in range(nq):
            right = await pg.evaluate("(()=>{const q=document.querySelector('#quizBox .q').textContent; const first=q.split('…')[0].trim(); const v=cur.verses.find(v=>first.startsWith(v[0].trim())); return v[1]})()")
            await pg.locator('#quizBox .opt', has_text=right).first.click(); await pg.wait_for_timeout(1000)
        check(await pg.evaluate('badges(cur).quiz') and 'شارة جديدة' in await pg.text_content('#quizBox'), 'a second kind passed: ⭐ awarded')
        await pg.click('#qBack')

        # ---- family theater (Leila + Baba) ----
        await pg.click('#back'); await pg.click('#grid .card[data-id="١"]'); await pg.wait_for_timeout(500)
        check(await pg.is_visible('#theaterBtn'), 'theater offered when two voices recorded the segment')
        await pg.click('#theaterBtn')
        names = set()
        for _ in range(40):
            if await pg.locator('#thShare').count(): break
            for el in await pg.locator('#verses .who').all_text_contents(): names.add(el.strip())
            await pg.wait_for_timeout(300)
        check(await pg.locator('#thShare').count() == 1, 'performance plays to the end')
        check(any('ليلى' in n for n in names) and any('بابا' in n for n in names), f'verses alternate between voices {names}')
        async with pg.expect_download() as dl:
            await pg.click('#thShare')
        wp = os.path.join(tempfile.mkdtemp(), 'f.wav'); await (await dl.value).save_as(wp)
        with wave.open(wp) as wv: secs = wv.getnframes() / wv.getframerate()
        check(secs > 2, f'family performance shared as one WAV ({secs:.1f}s)')
        await pg.click('#thAgain'); await pg.wait_for_timeout(300); await pg.click('#pbStop')

        # ---- certificate after memorising ----
        await pg.click('#back'); await pg.click('#grid .card[data-id="١٦"]'); await pg.wait_for_timeout(300)
        await pg.click('#modeSing'); await pg.click('#lvlBox .chip[data-l="4"]')
        await pg.click('#recBtn'); await pg.wait_for_timeout(7000); await pg.click('#recBtn'); await pg.wait_for_timeout(600)
        await pg.click('#keep'); await pg.wait_for_timeout(600)
        check('بانتظار' in await pg.text_content('#sheet') and await pg.locator('#celCert').count() == 0, 'a take from memory waits for the parent\'s stamp')
        await pg.click('#sheet button:has-text("تمام")')
        # the parent listens and stamps
        await pg.click('#back'); await pg.click('#goParent'); await pg.wait_for_timeout(700)
        check(await pg.locator('#pQueue [data-st="ok"]').count() >= 1, 'the parent page lists takes waiting to be heard, memorisation first')
        check('مهمة الليلة' in await pg.text_content('#pTonight'), 'the parent page proposes tonight\'s task')
        await pg.click('#pQueue [data-st="ok"] >> nth=0'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("badges(poemById('١٦')).mem"), 'the parent\'s stamp gives 🧠')
        await pg.click('#back'); await pg.wait_for_timeout(900)
        check('خُتم' in (await pg.text_content('#sheet') or '') and await pg.locator('#newsCert').count() == 1, 'the child is told, with the certificate')
        await pg.click('#newsCert'); await pg.wait_for_timeout(1500)
        cw = await pg.evaluate("document.querySelector('#certImg') && document.querySelector('#certImg').naturalWidth")
        check(cw == 1600, f'certificate image generated ({cw}px)')
        async with pg.expect_download() as dl:
            await pg.click('#cShare')
        check((await dl.value).suggested_filename.endswith('.png'), 'certificate saved as PNG')
        await pg.click('#pop', position={'x': 5, 'y': 5}); await pg.wait_for_timeout(200)
        await pg.click('#grid .card[data-id="١٦"]'); await pg.wait_for_timeout(500)
        check(await pg.is_visible('#certBtn'), '🏅 stays on the poem page')
        # the review comes back: due → listed at home → a take from memory moves it further away
        await pg.evaluate("st('١٦').rev[0].due=Date.now()-1000; saveS()")
        await pg.click('#back'); await pg.wait_for_timeout(300)
        check(await pg.locator('#reviewBox [data-rv="١٦"]').count() == 1, 'a memorised poem comes back for review on its day')
        await pg.click('#reviewBox [data-rv="١٦"]'); await pg.wait_for_timeout(400)
        await pg.click('#recBtn'); await pg.wait_for_timeout(7000); await pg.click('#recBtn'); await pg.wait_for_timeout(600)
        await pg.click('#keep'); await pg.wait_for_timeout(600)
        r = await pg.evaluate("st('١٦').rev[0]")
        r_ok = await pg.evaluate("st('١٦').rev[0].step===1 && st('١٦').rev[0].due>Date.now()+2*864e5")
        check(r_ok, 'a review from memory schedules the next one further away')
        await pg.click('#sheet button:has-text("تمام")')

        # ---- archive player shows a real length ----
        await pg.click('#back'); await pg.click('#goArchive'); await pg.wait_for_timeout(1500)
        await pg.click('#rlist .r >> nth=0 >> [data-pl]'); await pg.wait_for_timeout(1500)
        d = await pg.evaluate("[...document.querySelectorAll('#rlist audio')].map(a=>a.duration)")
        check(d and all(x and x != float('inf') for x in d), f'archive audio durations known {d[:3]}')
        check('٠:' in await pg.text_content('#rlist .r >> nth=1 >> [data-pl]'), 'each recording shows its length before loading')
        check(await pg.locator('#rlist .tag:has-text("🦜")').count() >= 1, 'marked models labelled in the archive')

        # ---- backup with recordings → restore into a fresh install ----
        await pg.click('#back'); await pg.click('#goParent'); await pg.click('#aExport'); await pg.wait_for_timeout(200)
        async with pg.expect_download() as dl:
            await pg.click('#exAll')
        bp = os.path.join(tempfile.mkdtemp(), 'b.json'); await (await dl.value).save_as(bp)
        n_rec = await pg.evaluate('recAll().then(a=>a.length)')
        ctx2 = await b.new_context(viewport={'width': 390, 'height': 844}); pg2 = await ctx2.new_page()
        await pg2.goto(URL); await pg2.wait_for_timeout(500)
        await pg2.evaluate("closeSheet(); gateUntil=Date.now()+600000"); await pg2.click('#goParent'); await pg2.set_input_files('#aImport', bp); await pg2.wait_for_timeout(1500)
        got = await pg2.evaluate('recAll().then(a=>a.length)')
        check(got == n_rec and n_rec > 0, f'backup carries recordings to a new install ({got}/{n_rec})')
        check('ليلى' in await pg2.text_content('#kidChip') and await pg2.evaluate("kidAge('ليلى')") == 7, 'children and ages restored')
        ok_audio = await pg2.evaluate("recAll().then(a=>decodeRec(a[0]).then(b=>b.duration>0))")
        check(ok_audio, 'restored audio still plays')
        await ctx2.close()

        check(not errs, f'no JS errors {errs}')
        await b.close()
    print(f'\n{len(fails)} failures')
    sys.exit(1 if fails else 0)

asyncio.run(main())
