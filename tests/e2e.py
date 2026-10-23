"""End-to-end check of www/index.html in Chromium with a fake microphone.
Run: python3 -m http.server -d www 8765 &  then  python3 tests/e2e.py
"""
import asyncio, sys
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

async def record(pg, secs=2.2):
    await pg.click('#recBtn'); await pg.wait_for_timeout(int(secs * 1000)); await pg.click('#recBtn'); await pg.wait_for_timeout(500)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, permissions=['microphone'], locale='ar-EG', accept_downloads=True)
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'fonts.g' not in m.text and 'ERR_' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(700)

        # first run: who are you
        check(await pg.locator('#kNew').count() == 1, 'first launch asks for the child name')
        await pg.click('#kNew'); await pg.fill('#pIn', 'سارة'); await pg.click('#pOk'); await pg.wait_for_timeout(200)
        check('سارة' in await pg.text_content('#kidChip'), 'kid chip shows the name')

        # home
        check(await pg.locator('#wk').count() == 1, 'weekly challenge banner shown')
        n_all = await pg.locator('#grid .card').count()
        await pg.click('#ages .chip[data-age="6"]'); n6 = await pg.locator('#grid .card').count()
        await pg.click('#ages .chip[data-age="9"]'); n9 = await pg.locator('#grid .card').count()
        await pg.click('#ages .chip[data-age="all"]')
        check(n_all == 31 and n6 + n9 == n_all, f'age filters partition the list ({n6}+{n9}={n_all})')
        check(not await pg.evaluate('document.documentElement.scrollWidth>innerWidth'), 'no horizontal overflow on phone')

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

        # record at level 4 → memorised segment
        await record(pg)
        check(await pg.locator('#keep').count() == 1, 'save sheet after recording')
        await pg.click('#keep'); await pg.wait_for_timeout(500)
        txt = await pg.text_content('#sheet')
        check('غيباً' in txt and '🎤' in txt, 'celebration mentions level and new 🎤 badge')
        await pg.click('#sheet .btn.p'); await pg.wait_for_timeout(100)
        check('🧠' in await pg.text_content('#segBox'), 'segment marked memorised')
        check(await pg.text_content('#timer') == '٠:٠٠', 'timer reset after stop')

        # too short
        await pg.click('#recBtn'); await pg.wait_for_timeout(500); await pg.click('#recBtn'); await pg.wait_for_timeout(400)
        check('قصير' in await pg.text_content('#toast'), 'too-short recording explained')

        # model recording
        await pg.click('#lvlBox .chip[data-l="1"]')
        await record(pg)
        await pg.check('#isModel'); await pg.fill('#who', 'بابا'); await pg.click('#keep'); await pg.wait_for_timeout(500)
        check(await pg.is_visible('#modelBtn'), 'model button appears after saving a model')
        check('سارة' in await pg.text_content('#kidChip'), 'saving a model does not switch the child')

        # second kid recording at level 1 for before/after
        await record(pg); await pg.click('#keep'); await pg.wait_for_timeout(400); await pg.click('#sheet .btn.p')

        # quizzes on a short poem
        await pg.click('#back'); await pg.click('#grid .card[data-id="١"]'); await pg.wait_for_timeout(200)
        await pg.click('#modeQuiz'); await pg.wait_for_timeout(100)
        check(await pg.locator('#quizBox [data-q]').count() == 3, 'three quiz types offered')
        await pg.click('#quizBox [data-q="complete"]')
        check(await pg.locator('#quizBox .opt').count() == 3, 'complete-the-verse has 3 options')
        for _ in range(5):
            right = await pg.evaluate("(()=>{const q=document.querySelector('#quizBox .q').textContent; const first=q.split('…')[0].trim(); const v=cur.verses.find(v=>first.startsWith(v[0].trim())); return v[1]})()")
            await pg.locator('#quizBox .opt', has_text=right).first.click(); await pg.wait_for_timeout(1000)
        check('٥ من ٥' in await pg.text_content('#quizBox'), 'perfect score registers')
        check('⭐' in await pg.text_content('#quizBox'), 'quiz badge awarded')
        await pg.click('#qMenu'); await pg.click('#quizBox [data-q="meaning"]'); await pg.wait_for_timeout(100)
        n_img = await pg.locator('#quizBox .imgs').count(); n_opt = await pg.locator('#quizBox .opt').count()
        check(n_opt == 3, f'meaning quiz has 3 options (image question: {bool(n_img)})')
        await pg.click('#quizBox .opt >> nth=0'); await pg.wait_for_timeout(1900)
        await pg.click('#modeQuiz'); await pg.click('#quizBox [data-q="order"]'); await pg.wait_for_timeout(100)
        order = await pg.evaluate('qs[qi]')
        for i in order:
            await pg.click(f'#quizBox .opt[data-i="{i}"]'); await pg.wait_for_timeout(80)
        await pg.wait_for_timeout(1300)
        check(await pg.evaluate('score') == 1, 'ordering round solved correctly scores')

        # story
        await pg.click('#modeStory'); await pg.wait_for_timeout(200)
        check(await pg.locator('#storyBox .scene').count() == 4, 'story shows 4 scenes')
        await pg.click('#storySing'); check(await pg.is_visible('#verses'), 'story → sing works')

        # archive
        await pg.click('#back'); await pg.click('#goArchive'); await pg.wait_for_timeout(500)
        check(await pg.locator('#rlist .r').count() == 3, 'archive lists 3 recordings')
        check(await pg.locator('#ba [data-ba]').count() == 1, 'before/after offered for the poem with 2 recordings')
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
        async with pg.expect_download() as dl:
            await pg.click('#goParent'); await pg.click('#aExport')
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

        # failed save is reported, not silently swallowed
        await pg.click('#grid .card[data-id="٤"]'); await pg.wait_for_timeout(200)
        await pg.evaluate('db.close()')
        await record(pg); await pg.click('#keep'); await pg.wait_for_timeout(300)
        check('تعذّر' in await pg.text_content('#toast') and await pg.locator('#keep').count() == 1, 'storage failure reported and the take is kept on screen')
        await pg.click('#redo')

        # persistence
        await pg.reload(); await pg.wait_for_timeout(600)
        check(await pg.locator('#kNew').count() == 0, 'no name prompt after reload')
        on = await pg.locator('#grid .card[data-id="٨"] .badges span.on').count()
        mem = await pg.evaluate("JSON.parse(localStorage.getItem('stats2'))['سارة']['٨'].mem")
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

asyncio.run(main())
