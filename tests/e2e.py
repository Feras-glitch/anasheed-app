"""End-to-end check of www/index.html in Chromium with a fake microphone.
Run: python3 -m http.server -d www 8765 &  then  python3 tests/e2e.py
"""
import asyncio, json, math, os, struct, sys, tempfile, wave
from playwright.async_api import async_playwright

def fake_voice():
    """A 'singing' microphone: 1.4 s tones with short pauses, so loudness and verse pauses are realistic."""
    path = os.path.join(tempfile.mkdtemp(), 'voice.wav'); rate = 16000
    with wave.open(path, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        fr = bytearray()
        for k in range(20):
            for i in range(int(rate * 1.6)):
                v = 0.0 if i > rate * 1.4 else 0.35 * math.sin(2 * math.pi * (220 + 30 * (k % 4)) * i / rate)
                fr += struct.pack('<h', int(v * 32767))
        w.writeframes(bytes(fr))
    return path

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

async def record(pg, secs=2.2):
    await pg.click('#recBtn'); await pg.wait_for_timeout(int(secs * 1000)); await pg.click('#recBtn'); await pg.wait_for_timeout(500)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', f'--use-file-for-fake-audio-capture={fake_voice()}'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, permissions=['microphone'], locale='ar-EG', accept_downloads=True)
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'fonts.g' not in m.text and 'ERR_' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(700)

        # first run: who are you
        check(await pg.locator('#kNew').count() == 1, 'first launch asks for the child name')
        await pg.click('#kNew'); await pg.fill('#pIn', 'سارة'); await pg.click('#pOk'); await pg.wait_for_timeout(200)
        await pg.click('#sheet [data-a="10"]'); await pg.wait_for_timeout(200)
        check('سارة' in await pg.text_content('#kidChip'), 'kid chip shows the name')

        # home
        check(await pg.locator('#wk').count() == 1, 'weekly challenge banner shown')
        mine = await pg.evaluate("[...document.querySelectorAll('#grid .card')].map(c=>poemById(c.dataset.id).age)")
        check(mine and all(a[0] <= 10 <= a[1] for a in mine), f'by default the list shows only poems for the child\'s age ({len(mine)})')
        await pg.click('#ages .chip[data-age="all"]'); n_all = await pg.locator('#grid .card').count()
        await pg.click('#ages .chip[data-age="6"]'); n6 = await pg.locator('#grid .card').count()
        await pg.click('#ages .chip[data-age="9"]'); n9 = await pg.locator('#grid .card').count()
        nine = await pg.evaluate("POEMS.filter(p=>p.age[0]<=9&&p.age[1]>=9).length")
        check(n9 >= nine, f'the 9–12 band includes every poem whose range reaches 9 ({n9} ≥ {nine})')
        await pg.click('#ages .chip[data-age="all"]')
        check(n_all == 31 and n6 + n9 >= n_all, f'every poem is in at least one band ({n6}+{n9}≥{n_all})')
        check(not await pg.evaluate('document.documentElement.scrollWidth>innerWidth'), 'no horizontal overflow on phone')
        th = await pg.evaluate("POEMS.filter(p=>p.poet==='أحمد شوقي').filter(p=>!thumbOf(p)).map(p=>p.title)")
        check(len(th) <= 3, f'fable cards carry a picture for children who cannot read (still without: {th})')
        w = await pg.evaluate("(()=>{const p=weekly(); return p && p.age[0]<=kidAge() && kidAge()<=p.age[1]})()")
        check(w, 'weekly poem fits the child\'s age')
        check(await pg.evaluate("Object.keys(localStorage).every(k=>k.startsWith('anasheed.'))"), 'every stored key is prefixed (shared web origin)')

        # parent gate: a short tap does not open the parent page; a 3-second press does
        await pg.click('#goParent'); await pg.wait_for_timeout(200)
        check(await pg.locator('#gateBtn').count() == 1 and await pg.evaluate('screen') == 'home', 'parent page asks for a long press')
        bb = await pg.locator('#gateBtn').bounding_box(); await pg.mouse.move(bb['x'] + 20, bb['y'] + 10)
        await pg.mouse.down(); await pg.wait_for_timeout(600); await pg.mouse.up(); await pg.wait_for_timeout(200)
        check(await pg.evaluate('screen') == 'home', 'a short press is not enough')
        await pg.mouse.down(); await pg.wait_for_timeout(3300); await pg.mouse.up(); await pg.wait_for_timeout(300)
        check(await pg.evaluate('screen') == 'parent', 'a 3-second press opens the parent page')
        await pg.click('#back'); await pg.wait_for_timeout(200)

        # long poem → segments + note
        await pg.click('#grid .card[data-id="٨"]'); await pg.wait_for_timeout(300)
        segs = await pg.locator('#segBox .chip').count()
        check(segs == 6, f'37-verse poem split into 6 segments (got {segs})')
        check(await pg.locator('#pNote .note').count() == 1, 'parent note shown on أم اليتيم')
        check(await pg.locator('#verses .verse').count() == 6, 'only the current segment is shown')
        await pg.click('#segBox .chip[data-s="2"]'); await pg.wait_for_timeout(150)
        check(await pg.get_attribute('#verses .verse >> nth=0', 'data-i') == '12', 'segment 3 starts at verse 13')
        check(await pg.locator('.vn').first.text_content() == '١٣', 'verse numbers in Arabic digits')

        # memorisation levels
        await pg.click('#modeSing'); await pg.wait_for_timeout(150)
        check(await pg.is_visible('#lvlBox'), 'level chips visible in sing mode')
        await pg.click('#lvlBox .chip[data-l="2"]')
        t2 = await pg.inner_html('#verses .verse >> nth=1')
        check('blank' in t2 and 'class="w' in t2, 'level 2 hides the second hemistich only')
        await pg.click('#lvlBox .chip[data-l="3"]')
        check('‥' in await pg.text_content('#verses'), 'level 3 shows first letters')
        await pg.click('#lvlBox .chip[data-l="4"]')
        check(await pg.locator('#verses .blank').count() == 12, 'level 4 blanks every hemistich')
        await pg.click('#verses .verse >> nth=2'); await pg.wait_for_timeout(100)
        check(await pg.locator('#verses .verse >> nth=2').locator('.blank').count() == 0, 'tapping a verse peeks at it')

        # a 3-second take at level 4 is too short for six verses: no 🧠
        await record(pg, 3.0)
        check(await pg.locator('#keep').count() == 1, 'save sheet after recording')
        await pg.click('#keep'); await pg.wait_for_timeout(500)
        txt = await pg.text_content('#sheet')
        check('🎤' in txt, 'celebration announces the new 🎤 badge')
        check('لتنال 🧠' in txt and '🧠' not in await pg.text_content('#segBox'), 'a take too short for the segment does not earn 🧠')
        await pg.click('#sheet button:has-text("تمام")'); await pg.wait_for_timeout(100)
        # the level cannot be switched to the full text mid-take
        await pg.click('#recBtn'); await pg.wait_for_timeout(700); await pg.click('#lvlBox .chip[data-l="1"]'); await pg.wait_for_timeout(100)
        check(await pg.evaluate('level') == 4, 'level locked while recording')
        await pg.wait_for_timeout(9800); await pg.click('#recBtn'); await pg.wait_for_timeout(600)
        await pg.click('#keep'); await pg.wait_for_timeout(500)
        txt = await pg.text_content('#sheet')
        check('غيباً! 🧠' in txt, 'celebration names the level reached')
        await pg.click('#sheet button:has-text("تمام")'); await pg.wait_for_timeout(100)
        check('🧠' in await pg.text_content('#segBox'), 'a whole, audible take from memory marks the segment memorised')
        check(await pg.text_content('#timer') == '٠:٠٠', 'timer reset after stop')

        # too short
        await pg.click('#recBtn'); await pg.wait_for_timeout(500); await pg.click('#recBtn'); await pg.wait_for_timeout(400)
        check('قصير' in await pg.text_content('#toast'), 'too-short recording explained')

        # double tap on ● starts one recorder only
        await pg.click('#lvlBox .chip[data-l="1"]')
        await pg.evaluate("window.__gum=0; const o=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices); navigator.mediaDevices.getUserMedia=c=>{window.__gum++; return new Promise(r=>setTimeout(r,300)).then(()=>o(c))}; 1")
        await pg.dblclick('#recBtn'); await pg.wait_for_timeout(2200); await pg.click('#recBtn'); await pg.wait_for_timeout(500)
        check(await pg.evaluate('__gum') == 1, 'a double tap on ● opens the microphone once')
        n0 = await pg.evaluate('recMeta().then(a=>a.length)')
        await pg.dblclick('#keep'); await pg.wait_for_timeout(600)
        check(await pg.evaluate('recMeta().then(a=>a.length)') == n0 + 1, 'a double tap on 💾 saves once')
        if await pg.locator('#sheet button:has-text("تمام")').count(): await pg.click('#sheet button:has-text("تمام")')
        # 🎧 while recording keeps the take
        await pg.click('#recBtn'); await pg.wait_for_timeout(2000); await pg.click('#goArchive'); await pg.wait_for_timeout(500)
        check(await pg.locator('#keep').count() == 1 and await pg.evaluate('screen') == 'poem', '🎧 during a recording stops it and offers to save it')
        await pg.click('#redo')

        # model recording (the parent gate is open from above, so the model box is offered)
        await record(pg)
        await pg.check('#isModel'); await pg.fill('#who', 'بابا'); await pg.click('#keep'); await pg.wait_for_timeout(500)
        check(await pg.is_visible('#modelBtn'), 'model button appears after saving a model')
        check('سارة' in await pg.text_content('#kidChip'), 'saving a model does not switch the child')

        # second kid recording at level 1 for before/after
        await record(pg); await pg.click('#keep'); await pg.wait_for_timeout(400); await pg.click('#sheet button:has-text("تمام")')

        # quizzes on a short poem
        await pg.click('#back'); await pg.click('#grid .card[data-id="١"]'); await pg.wait_for_timeout(200)
        await pg.click('#modeQuiz'); await pg.wait_for_timeout(100)
        check(await pg.locator('#quizBox [data-q]').count() == 3, 'three quiz types offered')
        await pg.click('#quizBox [data-q="complete"]')
        check(await pg.locator('#quizBox .opt').count() == 3, 'complete-the-verse has 3 options')
        nq = await pg.evaluate('qs.length')
        check(nq >= 3 and all(not v[0].rstrip().endswith('ـ') for v in await pg.evaluate('qs.map(i=>cur.verses[i])')), f'no question splits a word between question and answer ({nq} questions)')
        for _ in range(nq):
            right = await pg.evaluate("(()=>{const q=document.querySelector('#quizBox .q').textContent; const first=q.split('…')[0].trim(); const v=cur.verses.find(v=>first.startsWith(v[0].trim())); return v[1]})()")
            await pg.locator('#quizBox .opt', has_text=right).first.click(); await pg.wait_for_timeout(1000)
        check(await pg.evaluate('score') == nq, 'perfect score registers')
        check('⭐' in await pg.text_content('#quizBox'), 'quiz badge awarded')
        await pg.click('#qMenu'); await pg.click('#quizBox [data-q="meaning"]'); await pg.wait_for_timeout(100)
        n_img = await pg.locator('#quizBox .imgs').count(); n_opt = await pg.locator('#quizBox .opt').count()
        check(n_opt == 3, f'meaning quiz has 3 options (image question: {bool(n_img)})')
        opts = await pg.locator('#quizBox .opt').all_text_contents()
        opts = [o.strip() for o in opts if o.strip()]  # picture questions have no text
        check(not any(o[0] in 'وفب' and o[1:3] != 'ال' for o in opts), f'meaning options read naturally {opts}')
        await pg.click('#quizBox .opt >> nth=0'); await pg.wait_for_timeout(1900)
        # keys during a quiz do not throw the quiz away
        await pg.keyboard.press('Space'); await pg.wait_for_timeout(100)
        check(await pg.evaluate('mode') == 'quiz', 'space during a quiz keeps the quiz')
        await pg.click('#modeQuiz'); await pg.click('#quizBox [data-q="order"]'); await pg.wait_for_timeout(100)
        order = await pg.evaluate('qs[qi]')
        for i in order:
            await pg.click(f'#quizBox .opt[data-i="{i}"]'); await pg.wait_for_timeout(80)
        await pg.wait_for_timeout(1300)
        check(await pg.evaluate('score') == 1, 'ordering round solved correctly scores')

        # a finished quiz never awards a star to another poem
        await pg.click('#modeQuiz'); await pg.click('#quizBox [data-q="complete"]')
        nq = await pg.evaluate('qs.length')
        for _ in range(nq):
            right = await pg.evaluate("(()=>{const q=document.querySelector('#quizBox .q').textContent; const first=q.split('…')[0].trim(); const v=cur.verses.find(v=>first.startsWith(v[0].trim())); return v[1]})()")
            await pg.locator('#quizBox .opt', has_text=right).first.click()
            if _ < nq - 1: await pg.wait_for_timeout(1000)
        await pg.click('#back'); await pg.click('#grid .card[data-id="٦"]'); await pg.wait_for_timeout(1300)
        check(not await pg.evaluate("st('٦').quiz"), 'leaving right after the last answer gives no star to the next poem')
        await pg.click('#back'); await pg.click('#grid .card[data-id="١"]'); await pg.wait_for_timeout(200)

        # story: a whole picture book; 👂 only at its end
        await pg.evaluate("st('١').heard=0")
        await pg.click('#modeStory'); await pg.wait_for_timeout(300)
        check(await pg.locator('#storyBox .scene').count() == 4 and await pg.locator('#storyBox .sv').count() == 13, 'story shows 4 pictures and all 13 verses')
        check(not await pg.evaluate("st('١').heard"), 'opening the story does not earn 👂 yet')
        await pg.evaluate("document.querySelector('#storyEnd').scrollIntoView()"); await pg.wait_for_timeout(500)
        check(await pg.evaluate("!!st('١').heard"), 'reaching the end of the story earns 👂')
        await pg.click('#storySing'); check(await pg.is_visible('#verses'), 'story → sing works')
        # every control a child taps is at least 44 px
        small = await pg.evaluate("[...document.querySelectorAll('#poem .tools .btn, #lvlBox .chip, #bar .btn, header .btn')].filter(e=>e.offsetParent).map(e=>e.getBoundingClientRect()).filter(r=>Math.min(r.width,r.height)<40).length")
        check(small == 0, f'no small touch targets on the poem page ({small})')

        # archive
        await pg.click('#back'); await pg.click('#goArchive'); await pg.wait_for_timeout(500)
        check(await pg.locator('#rlist .r').count() == 5, 'archive lists 5 recordings')
        check(await pg.locator('#rlist audio').count() == 0, 'archive loads no audio until asked')
        await pg.click('#rlist .r >> nth=0 >> [data-pl]'); await pg.wait_for_timeout(800)
        check(await pg.locator('#rlist audio').count() == 1, 'tapping ▶ loads that one recording')
        check(await pg.locator('#ba [data-ba]').count() == 1, 'before/after offered for the poem with several recordings')
        async with pg.expect_download() as dl:
            await pg.click('#rlist .r >> nth=0 >> [data-sh]')
        fn = (await dl.value).suggested_filename
        check(fn.startswith('أنشودتي-') and fn.endswith('.wav'), f'share converts to WAV and falls back to download on desktop ({fn})')
        import wave, tempfile, os
        wp = os.path.join(tempfile.mkdtemp(), 'x.wav'); await (await dl.value).save_as(wp)
        with wave.open(wp) as w: secs = w.getnframes() / w.getframerate(); ch = w.getnchannels()
        check(1.5 < secs < 4 and ch == 1, f'WAV is valid mono audio of the right length ({secs:.1f}s)')
        await pg.click('#recFilter .chip:has-text("النماذج")'); await pg.wait_for_timeout(200)
        check(await pg.locator('#rlist .r').count() == 1, 'models filter')

        # parent page
        await pg.click('#goParent'); await pg.wait_for_timeout(300)
        k = await pg.text_content('#pKpis')
        check('أنشد' in k and 'حفظ' in k, 'parent KPIs rendered')
        check(await pg.locator('#pTable tr').count() >= 3, 'parent table lists active poems')
        await pg.fill('#aTitle', 'تجربة'); await pg.fill('#aText', 'بيت بلا فاصل')
        await pg.click('#aSave'); await pg.wait_for_timeout(100)
        check('السطر' in await pg.text_content('#toast'), 'malformed added poem rejected with line number')
        await pg.fill('#aText', 'شطر <img src=x onerror=window.__x=1> / شطر ب\nشطر ج / شطر د'); await pg.click('#aSave'); await pg.wait_for_timeout(200)
        check(await pg.locator('#addedList button').count() == 1, 'valid poem added')
        await pg.click('#back'); await pg.wait_for_timeout(200)
        check(await pg.locator('#grid .card').count() == 32, 'added poem on home')
        await pg.click('#grid .card >> nth=-1'); await pg.wait_for_timeout(150)
        await pg.wait_for_timeout(200); check('<img' in await pg.text_content('#verses') and not await pg.evaluate('window.__x'), 'user text is escaped, not injected')
        await pg.click('#back')
        await pg.click('#goParent'); await pg.click('#aExport')
        async with pg.expect_download() as dl:
            await pg.click('#exLite')
        check((await dl.value).suggested_filename.endswith('.json'), 'backup export downloads JSON')

        # ---- audit round 2 ----
        # homographs: the same written word gets the meaning of its own poem
        await pg.click('#back'); await pg.wait_for_timeout(200)
        await pg.click('#grid .card[data-id="١١"]'); await pg.wait_for_timeout(200)
        await pg.click('#verses .verse[data-i="3"] .w[data-k="بهر"]'); await pg.wait_for_timeout(150)
        txt = await pg.text_content('#sheet')
        check('أدهش' in txt and await pg.locator('#sheet img').count() == 0, 'بَهَرَ in Hafez means "dazzled", no cat picture')
        await pg.click('#mClose'); await pg.click('#back'); await pg.wait_for_timeout(200)
        await pg.click('#grid .card[data-id="٣٣"]'); await pg.wait_for_timeout(200)
        await pg.click('#verses .w[data-k="بهر"]'); await pg.wait_for_timeout(150)
        check('بقط' in await pg.text_content('#sheet') and await pg.locator('#sheet img').count() == 1, 'بِهِرٍّ in the cat fable keeps its meaning and picture')
        await pg.click('#mClose'); await pg.click('#back'); await pg.wait_for_timeout(200)
        await pg.click('#grid .card[data-id="٣٨"]'); await pg.wait_for_timeout(200)
        await pg.click('#segBox .chip[data-s="2"]')
        await pg.click('#verses .verse[data-i="12"] .w[data-k="بينا"]'); m13 = await pg.text_content('#sheet'); await pg.click('#mClose')
        await pg.click('#segBox .chip[data-s="0"]')
        await pg.click('#verses .verse[data-i="0"] .w[data-k="بينا"]'); m1 = await pg.text_content('#sheet'); await pg.click('#mClose')
        check('واضح' in m13 and 'بينما' in m1, 'verse-level meaning: بَيِّنا vs بَينا in the same poem')
        # parent edits a meaning for one verse only
        await pg.click('#verses .verse[data-i="0"] .w[data-k="بينا"]'); await pg.click('#sheet summary')
        await pg.fill('#mIn', 'معنى تجريبي'); await pg.click('#mSave'); await pg.wait_for_timeout(100)
        await pg.click('#segBox .chip[data-s="2"]')
        await pg.click('#verses .verse[data-i="12"] .w[data-k="بينا"]'); still = await pg.text_content('#sheet'); await pg.click('#mClose')
        await pg.click('#segBox .chip[data-s="0"]')
        await pg.click('#verses .verse[data-i="0"] .w[data-k="بينا"]'); edited = await pg.text_content('#sheet')
        check('معنى تجريبي' in edited and 'واضح' in still, 'parent edit applies to that verse only')
        await pg.click('#sheet summary'); await pg.click('#mDel'); await pg.wait_for_timeout(100)

        # following a poem to its end earns 👂 without any model
        await pg.click('#modeSing')
        check(not await pg.evaluate("!!st('٣٨').heard"), '👂 not given before the end')
        for _ in range(3):
            for _ in range(6): await pg.click('#nextV')
            if await pg.locator('#nextSeg').count(): await pg.click('#nextSeg')
        await pg.wait_for_timeout(200)
        check(await pg.evaluate("!!st('٣٨').heard"), 'reaching the last verse earns 👂 (no model needed)')

        # next-segment button at the end of a segment
        await pg.click('#back'); await pg.click('#grid .card[data-id="١٣"]'); await pg.wait_for_timeout(200)
        await pg.click('#segBox .chip[data-s="0"]'); await pg.click('#modeSing')
        for _ in range(6): await pg.click('#nextV')
        check(await pg.locator('#nextSeg').count() == 1, 'next-segment button shown at segment end')
        await pg.click('#nextSeg'); await pg.wait_for_timeout(150)
        check(await pg.get_attribute('#verses .verse >> nth=0', 'data-i') == '6', 'next segment opens')

        # save sheet survives a stray tap outside; back gesture doesn't drop it
        await record(pg)
        await pg.mouse.click(195, 40); await pg.wait_for_timeout(200)
        check(await pg.locator('#keep').count() == 1, 'tapping outside does not discard a recording')
        await pg.go_back(); await pg.wait_for_timeout(300)
        check(await pg.locator('#keep').count() == 1 and await pg.evaluate('screen') == 'poem', 'back gesture does not discard a recording')
        await pg.click('#redo'); await pg.wait_for_timeout(100)

        # back gesture navigation
        await pg.go_back(); await pg.wait_for_timeout(300)
        check(await pg.evaluate('screen') == 'home', 'back gesture returns to home')
        await pg.click('#grid .card >> nth=0'); await pg.wait_for_timeout(100); await pg.click('#back'); await pg.click('#grid .card >> nth=1'); await pg.wait_for_timeout(400)
        check(await pg.evaluate('screen') == 'poem', 'fast back-then-open is not bounced to home')
        await pg.click('#back')

        # the storage connection drops (iOS in the background): the app reconnects and saves
        await pg.click('#grid .card[data-id="٤"]'); await pg.wait_for_timeout(200)
        n0 = await pg.evaluate('recMeta().then(a=>a.length)')
        await pg.evaluate('db.close()')
        await record(pg); await pg.click('#keep'); await pg.wait_for_timeout(600)
        check(await pg.evaluate('recMeta().then(a=>a.length)') == n0 + 1, 'saving still works after the storage connection dropped')
        if await pg.locator('#sheet button:has-text("تمام")').count(): await pg.click('#sheet button:has-text("تمام")')
        # storage really gone: the failure is reported, the take stays, and it can be sent away
        await pg.evaluate("db.close(); db=null; indexedDB.open=()=>{ throw new Error('gone') }; 1")
        await record(pg); await pg.click('#keep'); await pg.wait_for_timeout(400)
        check('تعذّر' in await pg.text_content('#saveErr') and await pg.locator('#keep').count() == 1 and await pg.locator('#saveShare').count() == 1, 'storage failure reported, the take kept, and it can be sent away')
        await pg.click('#redo')

        # persistence
        await pg.reload(); await pg.wait_for_timeout(600)
        check(await pg.locator('#kNew').count() == 0, 'no name prompt after reload')
        on = await pg.locator('#grid .card[data-id="٨"] .badges span.on').count()
        mem = await pg.evaluate("JSON.parse(localStorage.getItem('anasheed.stats2'))['سارة']['٨'].mem")
        check(on == 1 and mem == [2], f'progress persists (🎤 on, segment 3 memorised: {mem})')

        check(not errs, f'no JS errors {errs}')

        # migration from the previous single-child version
        ctx2 = await b.new_context(viewport={'width': 390, 'height': 844})
        pg2 = await ctx2.new_page()
        await pg2.goto(URL); await pg2.evaluate("localStorage.clear(); localStorage.setItem('who', JSON.stringify('أحمد')); localStorage.setItem('stats', JSON.stringify({'١':{rec:2,quiz:5}}))")
        await pg2.reload(); await pg2.wait_for_timeout(500)
        check('أحمد' in await pg2.text_content('#kidChip'), 'old single-child data migrates to a profile')
        check(await pg2.locator('#grid .card[data-id="١"] .badges span.on').count() == 2, 'old recordings/quiz become badges')
        await b.close()
    print(f'\n{len(fails)} failures')
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    asyncio.run(main())
