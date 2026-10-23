"""Drive the real APK on an Android emulator through the WebView DevTools socket.

usage: python3 tests/android_device.py <apk> <outdir>
Writes <outdir>/results.json and screenshots. Never aborts midway: every step's
outcome (or error) is recorded so a single failure doesn't hide the rest.
"""
import json, os, re, subprocess, sys, time, urllib.request
import websocket  # pip install websocket-client

APK, OUT = sys.argv[1], sys.argv[2]
PKG = 'com.feras.anasheed'
os.makedirs(OUT, exist_ok=True)
R = {}

def adb(*a):
    return subprocess.run(['adb', *a], capture_output=True, text=True).stdout

def shot(name):
    png = subprocess.run(['adb', 'exec-out', 'screencap', '-p'], capture_output=True).stdout
    open(os.path.join(OUT, name + '.png'), 'wb').write(png)

def focus():
    m = re.search(r'mCurrentFocus=Window\{[^ ]+ [^ ]+ ([^}]+)\}', adb('shell', 'dumpsys', 'window'))
    return m.group(1) if m else ''

def step(name, fn):
    try:
        R[name] = fn()
    except Exception as e:  # keep going
        R[name] = {'error': repr(e)[:600]}
    print(name, '→', json.dumps(R[name], ensure_ascii=False)[:600], flush=True)

ws = None; mid = 0
def connect():
    global ws
    pid = ''
    for _ in range(30):
        pid = adb('shell', 'pidof', PKG).strip()
        if pid: break
        time.sleep(1)
    socks = adb('shell', 'cat', '/proc/net/unix')
    name = next((s for s in re.findall(r'@(webview_devtools_remote_\d+)', socks) if s.endswith('_' + pid)), None)
    adb('forward', '--remove-all')
    adb('forward', 'tcp:9222', 'localabstract:' + name)
    for _ in range(20):
        try:
            targets = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=5))
            page = next(t for t in targets if t.get('type') == 'page')
            ws = websocket.create_connection(page['webSocketDebuggerUrl'], suppress_origin=True, timeout=60)
            return {'pid': pid, 'socket': name, 'url': page.get('url')}
        except Exception:
            time.sleep(1)
    raise RuntimeError('devtools not reachable')

def ev(expr):
    global mid
    mid += 1
    ws.send(json.dumps({'id': mid, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True, 'returnByValue': True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == mid:
            r = m.get('result', {})
            if 'exceptionDetails' in r:
                raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:500])
            return r.get('result', {}).get('value')

def cdp(method, params):
    global mid
    mid += 1
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == mid:
            return m

def tap(sel):  # a trusted touch through DevTools, like a child's finger
    xy = ev("(()=>{const e=document.querySelector(%s); e.scrollIntoView({block:'center'}); const b=e.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]})()" % json.dumps(sel))
    for t in ('mousePressed', 'mouseReleased'):
        cdp('Input.dispatchMouseEvent', {'type': t, 'x': xy[0], 'y': xy[1], 'button': 'left', 'clickCount': 1})
    time.sleep(0.8)

def launch():
    adb('shell', 'am', 'start', '-W', '-n', f'{PKG}/.MainActivity')
    time.sleep(6)
    return connect()

R['install'] = adb('install', '-r', APK).strip()[-200:]
adb('shell', 'pm', 'grant', PKG, 'android.permission.RECORD_AUDIO')
R['device'] = {'sdk': adb('shell', 'getprop', 'ro.build.version.sdk').strip(), 'webview': re.findall(r'versionName=(\S+)', adb('shell', 'dumpsys', 'package', 'com.google.android.webview'))[:1]}
step('launch', launch)
shot('01-first-launch')

step('facts', lambda: ev("""(async()=>({href:location.href, secure:isSecureContext, native:Capacitor.isNativePlatform(),
  plugins:Object.keys(Capacitor.Plugins||{}).filter(k=>/Share|Filesystem/.test(k)), cards:document.querySelectorAll('#grid .card').length,
  kidSheet:!!document.querySelector('#kNew'), mediaRecorder:typeof MediaRecorder,
  types:Object.fromEntries(['audio/mp4','audio/mp4;codecs=mp4a.40.2','audio/webm;codecs=opus'].map(t=>[t,typeof MediaRecorder!=='undefined'&&MediaRecorder.isTypeSupported(t)])),
  headerTop:document.querySelector('header').getBoundingClientRect().top, chipTop:document.querySelector('#kidChip').getBoundingClientRect().top,
  safeTop:getComputedStyle(document.querySelector('header')).paddingTop, innerW:innerWidth, innerH:innerHeight, dpr:devicePixelRatio,
  fonts: await document.fonts.load('700 20px Amiri','أ').then(f=>f.length>0), fontCairo: await document.fonts.load('700 16px Cairo','أ').then(f=>f.length>0), screenH:screen.height, loadMs:Math.round(performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd)}))()"""))

step('make_kid', lambda: ev("kids.push('تجربة'); LS.set('kids',kids); closeSheet(); setKid('تجربة'); kid"))
time.sleep(1); shot('02-home')

def back_test():
    ev("closeSheet(); show('home',true); renderHome(); 'ok'")
    tap('#grid .card[data-id="١"]'); shot('03-poem')
    out = {'opened_by_tap': ev('screen')}
    tap('#verses .w.has'); out['sheet_open'] = ev("document.querySelector('#pop').classList.contains('on')")
    adb('shell', 'input', 'keyevent', '4'); time.sleep(1.2)
    out['back1_sheet_closed'] = ev("!document.querySelector('#pop').classList.contains('on')"); out['back1_screen'] = ev('screen')
    adb('shell', 'input', 'keyevent', '4'); time.sleep(1.2)
    out['back2_screen'] = ev('screen'); out['back2_app_open'] = PKG in focus()
    adb('shell', 'input', 'keyevent', '4'); time.sleep(2)
    out['back3_exits_from_home'] = PKG not in focus()
    if out['back3_exits_from_home']:
        out['relaunch'] = launch()
    return out
step('back_button', back_test)

def record_test():
    ev("openPoem('١'); document.querySelector('#recBtn').click(); 'clicked'")
    time.sleep(4); shot('04-recording')
    live = ev("document.querySelector('#recBtn').classList.contains('live')")
    sheet = ev("document.querySelector('#sheet').innerText.slice(0,200)")
    ev("document.querySelector('#recBtn').click(); 'stop'"); time.sleep(2); shot('05-save-sheet')
    has_keep = ev("!!document.querySelector('#keep')")
    if has_keep:
        ev("document.querySelector('#keep').click(); 'kept'"); time.sleep(2); shot('06-celebrate')
    recs = ev("recAll().then(a=>a.map(r=>({size:r.blob.size,type:r.type,dur:Math.round(r.dur)})))")
    return {'live_while_recording': live, 'sheet_text_if_error': sheet if not live else '', 'save_sheet': has_keep, 'recordings': recs}
step('record', record_test)

def playback_test():
    return ev("""(async()=>{ const a=(await recAll())[0]; if(!a) return 'no recording';
      const au=new Audio(URL.createObjectURL(a.blob)); await new Promise((res,rej)=>{au.onloadedmetadata=res; au.onerror=()=>rej(au.error&&au.error.code); setTimeout(()=>rej('timeout'),8000)});
      return {duration: au.duration}; })()""")
step('playback', playback_test)

step('filesystem_plugin', lambda: ev("Capacitor.Plugins.Filesystem.writeFile({path:'t.txt',data:btoa('hi'),directory:'CACHE'}).then(w=>w.uri)"))

def share_test():
    ev("closeSheet(); recAll().then(a=>{ shareRec(a[0]); return 'called' })")
    time.sleep(4); shot('07-share-sheet')
    f = focus()
    adb('shell', 'input', 'keyevent', '4'); time.sleep(1.5)
    return {'focus_during_share': f, 'focus_after_dismiss': focus()}
step('share', share_test)

def level4():
    ev("openPoem('١'); $('#modeSing').click(); document.querySelector('#lvlBox .chip[data-l=\"3\"]').click(); 'ok'")
    time.sleep(1); shot('08-level3')
    return ev("document.querySelectorAll('#verses .hid').length")
step('level3_render', level4)

def rotate():
    adb('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
    adb('shell', 'settings', 'put', 'system', 'user_rotation', '1'); time.sleep(2.5); shot('09-landscape')
    w = ev("({w:innerWidth,h:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth})")
    adb('shell', 'settings', 'put', 'system', 'user_rotation', '0'); time.sleep(1.5)
    return w
step('landscape', rotate)

def features():
    out = {}
    ev("closeSheet(); startModel('١',0); 'ok'"); time.sleep(1.5)
    ev("document.querySelector('#recBtn').click(); 'rec'"); time.sleep(2.5)
    out['vu_visible'] = ev("document.querySelector('#bar').classList.contains('recording')")
    for _ in range(2):
        ev("document.querySelector('#nextV').click(); 'n'"); time.sleep(1.6)
    ev("document.querySelector('#recBtn').click(); 's'"); time.sleep(2)
    ev("document.querySelector('#keep').click(); 'k'"); time.sleep(2)
    out['next_sheet'] = ev("!!document.querySelector('#mnStop')")
    ev("document.querySelector('#mnStop') && document.querySelector('#mnStop').click(); 'c'"); time.sleep(1)
    out['echo_button'] = ev("getComputedStyle(document.querySelector('#echoBtn')).display!=='none'")
    ev("document.querySelector('#echoBtn').click(); 'e'"); time.sleep(2.5); shot('11-echo')
    out['echo_bar'] = ev("document.querySelector('#pbText').textContent")
    l1 = ev('curLine'); time.sleep(5); out['echo_moves'] = [l1, ev('curLine')]
    ev("stopPlay(); 's'")
    out['certificate_px'] = ev("certificate(cur).then(()=>new Promise(r=>setTimeout(r,1500))).then(()=>{const i=document.querySelector('#certImg'); return i?i.naturalWidth:0})")
    shot('12-certificate')
    ev("closeSheet(); 'c'")
    out['picture_file'] = ev("(()=>{const s=STORY['١'][0].img; return s.slice(0,12)})()")
    return out
step('features', features)

def persistence():
    adb('shell', 'am', 'force-stop', PKG); time.sleep(1)
    launch()
    return ev("recAll().then(a=>({kid, recordings:a.length, stats:JSON.stringify(S).length}))")
step('persist_after_restart', persistence)
shot('10-after-restart')

json.dump(R, open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False, indent=1)
print('done')
