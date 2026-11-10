"""A ready pack with a whole lesson («وصية لاجئ»): the parent types the poem, the app brings the lesson around it.
The test types dummy lines made of the pack's key words only — never the poem. Run with the same server as tests/e2e.py."""
import asyncio, json, sys
from playwright.async_api import async_playwright

URL = 'http://localhost:8765/index.html'
fails = []
def check(cond, msg):
    print(('✓ ' if cond else '✗ ') + msg)
    if not cond: fails.append(msg)

PACK = json.load(open('content/packs.json', encoding='utf-8'))['وصية لاجئ']

async def main():
    # one dummy line per verse, from its first key; line 30 is left out, as a parent might skip one
    lines = [f'{k[0]} سطر / تجريبي {i + 1}' for i, k in enumerate(PACK['keys'])]
    lines[0] = 'الغسق سطر / تجريبي ١'
    typed = lines[:29] + lines[30:]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 360, 'height': 740})
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(700)
        await pg.evaluate('closeSheet(); renderAdded()')
        check('«وصية لاجئ»' in await pg.evaluate("$('#packList').innerHTML") and 'العمود الأيمن' in await pg.evaluate("$('#packList').innerHTML"), 'the parent is told how to type «وصية لاجئ»')
        await pg.evaluate("([t])=>{ $('#aTitle').value='وصية لاجئ'; $('#aPoet').value='هاشم الرفاعي'; $('#aText').value=t; $('#aSave').click(); }", ['\n'.join(typed)])
        await pg.wait_for_timeout(400)
        pid = await pg.evaluate("added[added.length-1].id")
        r = json.loads(await pg.evaluate(f"JSON.stringify((p=>({{pack:p.pack, age:p.age, n:p.verses.length}}))(poemById('{pid}')))"))
        check(r == {'pack': 'وصية لاجئ', 'age': [9, 12], 'n': 43}, f'the typed poem is recognised, with its age band {r}')
        v = json.loads(await pg.evaluate(f"JSON.stringify(BAYT['{pid}'].v)"))
        check(len(v) == 43 and v[0] == PACK['bayt'][0] and v[28] == PACK['bayt'][28] and v[29] == PACK['bayt'][30], 'each typed line gets its own meaning, also after the missing line')
        await pg.evaluate(f"closeSheet(); openPoem('{pid}'); closeSheet()"); await pg.wait_for_timeout(300)
        check(await pg.evaluate("M('الغسق',0)") == 'ظلام الليل' and await pg.evaluate("M('البطاح',31)") is not None, 'the lesson\'s glossary answers a tap on a word')
        check(await pg.locator('#lessonBtn').is_visible() and await pg.locator('#taleBtn').is_visible() and await pg.locator('#talkBtn').is_visible(), 'the lesson, the tale and the talk questions are there')
        await pg.click('#lessonBtn'); await pg.wait_for_timeout(300)
        sh = await pg.text_content('#sheet')
        check(await pg.locator('#sheet details.ls').count() == 6 and await pg.locator('#sheet details.ls[open]').count() == 1, 'five ideas and the textbook answers, the first idea open')
        check('هاشم الرفاعي شاعرٌ مصري' in sh and 'الفكرة الأولى: معاناة اللاجئ الفلسطيني وذكرياته' in sh and 'الفكرة الخامسة' in sh, 'poet, occasion and the five ideas')
        first = await pg.text_content('#sheet details.ls >> nth=0')
        check('الغسق سطر' in first and 'سيلفّني ويغطّيني' in first and 'أسلوب نداء غرضه التحبّب والتقرّب' in first, 'an idea shows the lines as the parent typed them, the words and the analysis')
        third = await pg.text_content('#sheet details.ls >> nth=2')
        check('السطر ٣٠ لم يُكتب في النشيد' in third, 'a line the parent left out is named, not invented')
        q = pg.locator('#sheet details.ls >> nth=0').locator('details.qa >> nth=0')
        check(not await q.locator('p').is_visible(), 'a discussion answer stays hidden')
        await q.locator('summary').click(); await pg.wait_for_timeout(100)
        check(await q.locator('p').is_visible(), '…until the child taps the question')
        book = await pg.text_content('#sheet details.ls >> nth=5')
        check('الفهم والاستيعاب' in book and 'اللغة والأسلوب' in book and 'لأنّ عين الجناة لم تبكِ' in book, 'the textbook answers as in the lesson file')
        await pg.evaluate('closeSheet()')
        await pg.click('#modeQuiz'); await pg.wait_for_timeout(200)
        if await pg.locator('#quizBox [data-q="sense"]').count():
            check('(تدريب)' in await pg.text_content('#quizBox [data-q="sense"]'), '«ما معنى البيت؟» has no wrong meanings written for this pack: practice')
        check(not errs, f'no page errors {errs[:2]}')
        await b.close()
    print(f'\n{len(fails)} failures'); sys.exit(1 if fails else 0)

asyncio.run(main())
