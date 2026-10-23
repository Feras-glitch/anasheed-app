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
bg = os.path.join(res, 'values', 'ic_launcher_background.xml')
open(bg, 'w').write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#EBCB9A</color>\n</resources>\n')

g = os.path.join(A, 'build.gradle')
s = open(g, encoding='utf-8').read()
ver = os.environ.get('APP_VERSION', '1.0.0')
code = os.environ.get('GITHUB_RUN_NUMBER', '1')
s = re.sub(r'versionCode \d+', f'versionCode {code}', s)
s = re.sub(r'versionName "[^"]*"', f'versionName "{ver}"', s)
s += '''
android {
    signingConfigs {
        debug {
            storeFile file("../../keys/anasheed.p12")
            storePassword "android"
            keyAlias "anasheed"
            keyPassword "android"
        }
    }
}
'''
open(g, 'w', encoding='utf-8').write(s)
print('android patched: mic permission, icons, signing, version', ver, code)
