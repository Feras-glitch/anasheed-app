"""Run after `npx cap add android`: microphone permission, icons, fixed signing key, version."""
import os, re, shutil
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(R, 'android', 'app')

man = os.path.join(A, 'src', 'main', 'AndroidManifest.xml')
s = open(man, encoding='utf-8').read()
for perm in ('RECORD_AUDIO', 'MODIFY_AUDIO_SETTINGS'):
    tag = f'<uses-permission android:name="android.permission.{perm}" />'
    if tag not in s:
        s = s.replace('</manifest>', f'    {tag}\n</manifest>')
open(man, 'w', encoding='utf-8').write(s)

res = os.path.join(A, 'src', 'main', 'res')
for d in os.listdir(os.path.join(R, 'icons', 'android')):
    for f in os.listdir(os.path.join(R, 'icons', 'android', d)):
        os.makedirs(os.path.join(res, d), exist_ok=True)
        shutil.copy(os.path.join(R, 'icons', 'android', d, f), os.path.join(res, d, f))
# Android 15 forces edge-to-edge for targetSdk 35 and the WebView doesn't report safe-area insets,
# so the header slid under the status bar. Opt out: the app is laid out between the system bars.
sty = os.path.join(res, 'values', 'styles.xml')
x = open(sty, encoding='utf-8').read()
item = '<item name="android:windowOptOutEdgeToEdgeEnforcement">true</item>'
if item not in x:
    x = re.sub(r'(<style name="AppTheme\.NoActionBar(?:Launch)?"[^>]*>)', r'\1\n        ' + item, x)
    assert item in x, 'styles.xml: AppTheme.NoActionBar not found'
open(sty, 'w', encoding='utf-8').write(x)
bg = os.path.join(res, 'values', 'ic_launcher_background.xml')
open(bg, 'w').write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#EBCB9A</color>\n</resources>\n')

g = os.path.join(A, 'build.gradle')
s = open(g, encoding='utf-8').read()
ver = os.environ.get('APP_VERSION', '1.0.0')
code = os.environ.get('GITHUB_RUN_NUMBER', '1')
s = re.sub(r'versionCode \d+', f'versionCode {code}', s)
s = re.sub(r'versionName "[^"]*"', f'versionName "{ver}"', s)
# the signing key lives in GitHub Secrets (ANDROID_KEYSTORE base64 + ANDROID_KEYSTORE_PASSWORD), never in the repo
ks = os.environ.get('ANDROID_KEYSTORE_PATH', '')
pw = os.environ.get('ANDROID_KEYSTORE_PASSWORD', '')
if not (ks and os.path.exists(ks) and pw):
    raise SystemExit('missing signing key: add ANDROID_KEYSTORE and ANDROID_KEYSTORE_PASSWORD in Settings → Secrets → Actions')
# the shipped APK is a release build (not debuggable: nobody with a cable can read the children's recordings).
# The debug build used by the emulator test keeps Gradle's own throwaway debug key: signed with another key,
# it can never be installed over a family's app to read its data.
s += f'''
android {{
    signingConfigs {{
        release {{
            storeFile file("{ks}")
            storePassword System.getenv("ANDROID_KEYSTORE_PASSWORD")
            keyAlias "anasheed"
            keyPassword System.getenv("ANDROID_KEYSTORE_PASSWORD")
        }}
    }}
    buildTypes {{
        release {{
            signingConfig signingConfigs.release
        }}
    }}
}}
'''
open(g, 'w', encoding='utf-8').write(s)
print('android patched: mic permission, icons, signing, version', ver, code)
