"""The published APK itself on the emulator (the device test before it drives the debug build, which the release is not).

usage: python3 tests/android_release.py <release apk> <outdir> [<previous release apk>]

It installs over the previous release when one is given (same key: a family's recordings stay), then starts and shows
its window. Its certificate and that it is not debuggable are checked in the workflow before the emulator starts.
Writes <outdir>/release.json and release.png; exits 1 when a check fails (the release waits for this job).
"""
import json, os, re, subprocess, sys, time

APK, OUT = sys.argv[1], sys.argv[2]
PREV = sys.argv[3] if len(sys.argv) > 3 and os.path.isfile(sys.argv[3]) and os.path.getsize(sys.argv[3]) > 0 else None
PKG = 'com.feras.anasheed'
os.makedirs(OUT, exist_ok=True)
R = {}

def adb(*a, timeout=300):
    r = subprocess.run(['adb', *a], capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()

def version():
    m = re.search(r'versionName=(\S+)', adb('shell', 'dumpsys', 'package', PKG))
    return m.group(1) if m else ''

def started(secs=30):
    for _ in range(secs):
        if adb('shell', 'pidof', PKG): return True
        time.sleep(1)
    return False

def focus():
    m = re.search(r'mCurrentFocus=Window\{[^ ]+ [^ ]+ ([^}]+)\}', adb('shell', 'dumpsys', 'window'))
    return m.group(1) if m else ''

def launch():
    adb('shell', 'am', 'start', '-W', '-n', f'{PKG}/.MainActivity')
    ok = started(); time.sleep(6)
    return ok

# the debug build of the device test carries another key: it must go before a release can be installed
R['uninstall_debug'] = adb('uninstall', PKG)
if PREV:
    R['install_previous'] = adb('install', PREV)
    R['previous_version'] = version()
    R['previous_starts'] = launch()
    adb('shell', 'am', 'force-stop', PKG)
    # the update a family receives: installed over the previous release, keeping its data
    R['install'] = adb('install', '-r', APK)
else:
    R['install'] = adb('install', APK)
R['version'] = version()
R['starts'] = launch()
R['focus'] = focus()
R['pid'] = adb('shell', 'pidof', PKG)
open(os.path.join(OUT, 'release.png'), 'wb').write(subprocess.run(['adb', 'exec-out', 'screencap', '-p'], capture_output=True).stdout)
json.dump(R, open(os.path.join(OUT, 'release.json'), 'w'), ensure_ascii=False, indent=1)

want = os.environ.get('APP_VERSION', '')
CHECKS = {
    'installs' + (' over the previous release' if PREV else ''): 'Success' in R['install'],
    'previous release installed first': (not PREV) or 'Success' in R.get('install_previous', ''),
    'is the version being released': (not want) or R['version'] == want,
    'starts': R['starts'] is True and bool(R['pid']),
    'shows its window': PKG in R['focus'],
}
for k, ok in CHECKS.items():
    print(('✓ ' if ok else '✗ ') + k)
print(json.dumps(R, ensure_ascii=False)[:1500])
bad = [k for k, ok in CHECKS.items() if not ok]
if bad:
    print('::error title=release APK::' + ' · '.join(bad))
    sys.exit(1)
print('release APK: done')
