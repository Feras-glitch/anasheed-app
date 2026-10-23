"""Safari-engine (WebKit) smoke test — the closest to an iPhone that CI can run.
No microphone in WebKit's headless mode, so recordings are synthesised in the page (a WAV with
three tones = three 'verses') and stored exactly like real ones; then echo, theater, quiz,
story and certificate run on WebKit's own audio/canvas/IndexedDB.
usage: python tests/webkit_smoke.py [webkit|chromium]"""
import asyncio, sys
from playwright.async_api import async_playwright

import os
URL = os.environ.get('APP_URL', 'http://localhost:8765/index.html')
ENGINE = sys.argv[1] if len(sys.argv) > 1 else 'webkit'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

SYNTH = """async (who) => {
  // three 1.2 s tones separated by 0.5 s of silence, like three sung verses
  const rate=22050, seg=1.2, gap=0.5, n=Math.round(rate*(3*seg+3*gap)), off=new OfflineAudioContext(1,n,rate);
  const buf=off.createBuffer(1,n,rate), d=buf.getChannelData(0);
  for(let k=0;k<3;k++){ const s0=Math.round(rate*(gap+k*(seg+gap))); for(let i=0;i<rate*seg;i++) d[s0+i]=0.3*Math.sin(2*Math.PI*(330+110*k)*i/rate); }
  const blob=await bufferToWav(buf);
  return await recPut({poem:'١',title:cur.title,who,when:Date.now(),dur:n/rate,blob,type:'audio/wav',lvl:1,seg:0,
    model: who==='بابا', marks:[[0,0],[1,gap+seg+0.2],[2,gap+2*(seg+gap)+0.2]], loud:0.6});
}"""

async def main():
    async with async_playwright() as p:
        b = await getattr(p, ENGINE).launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, accept_downloads=True)
        pg = await ctx.new_page(); pg.set_default_timeout(20000)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(800)
        check(await pg.locator('#kNew').count() == 1, f'{ENGINE}: app starts and asks for the child')
        await pg.click('#kNew'); await pg.fill('#pIn', 'ليلى'); await pg.click('#pOk'); await pg.wait_for_timeout(200)
        await pg.click('#sheet [data-a="7"]'); await pg.wait_for_timeout(200)
        check(await pg.locator('#grid .card').count() > 5, 'poem list renders')
        await pg.click('#grid .card[data-id="١"]'); await pg.wait_for_timeout(300)
        await pg.click('#verses .w.img >> nth=0'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("document.querySelector('#sheet img').naturalWidth") > 100, 'word picture loads')
        await pg.click('#mClose')
        await pg.click('#modeStory'); await pg.wait_for_timeout(500)
        check(await pg.evaluate("[...document.querySelectorAll('#storyBox img')].every(i=>i.naturalWidth>0)"), 'story pictures load')
        await pg.click('#modeQuiz'); await pg.click('#quizBox [data-q="complete"]'); await pg.wait_for_timeout(100)
        check(await pg.locator('#quizBox .opt').count() == 3, 'quiz renders')

        # synthetic recordings through the same storage path as real ones
        ids = [await pg.evaluate(SYNTH, 'بابا'), await pg.evaluate(SYNTH, 'ليلى')]
        check(all(i is not None for i in ids), 'recordings saved to IndexedDB (Blob storage)')
        await pg.evaluate("loadModel()"); await pg.wait_for_timeout(400)
        check(await pg.is_visible('#echoBtn') and await pg.is_visible('#theaterBtn'), 'echo and theater offered')
        sp = await pg.evaluate("recAll().then(a=>decodeRec(a[0]).then(b=>spans(a[0],b)))")
        check(sp and len(sp) == 3, f'verse spans found by silence {sp}')
        await pg.evaluate("window.__seen=new Set(); setInterval(()=>__seen.add(curLine),50)")
        await pg.click('#modelBtn'); await pg.wait_for_timeout(5500)
        seen = await pg.evaluate("[...__seen]")
        check({0, 1, 2} <= set(seen), f'karaoke walks the verses {sorted(seen)}')
        await pg.click('#echoBtn'); turn = False
        for _ in range(24):
            if 'دورك' in (await pg.text_content('#pbText') or ''): turn = True; break
            await pg.wait_for_timeout(250)
        check(turn, 'echo gives the child a turn'); await pg.click('#pbStop')
        await pg.click('#theaterBtn')
        for _ in range(70):
            if await pg.locator('#thShare').count(): break
            await pg.wait_for_timeout(300)
        ok = await pg.locator('#thShare').count() == 1
        check(ok, 'family theater plays to the end' + ('' if ok else f" — bar: {await pg.text_content('#pbText')!r}, sheet: {(await pg.text_content('#sheet') or '')[:80]!r}, errors: {errs}"))
        if ok:
            await pg.click('#thAgain'); await pg.wait_for_timeout(200); await pg.click('#pbStop')
        w = await pg.evaluate("bufferToWav(actx().createBuffer(1,22050,22050)).then(b=>b.size)")
        check(w > 40000, 'WAV export works')
        await pg.evaluate("certificate(cur)"); await pg.wait_for_timeout(2000)
        check(await pg.evaluate("(document.querySelector('#certImg')||{}).naturalWidth") == 1600, 'certificate drawn on canvas')
        check(not errs, f'no JS errors {errs}')
        await b.close()
    print(f'\n{len(fails)} failures'); sys.exit(1 if fails else 0)

async def guarded():
    try:
        await asyncio.wait_for(main(), 300)
    except asyncio.TimeoutError:
        print('✗ timed out after the last ✓ above'); sys.exit(1)
asyncio.run(guarded())
