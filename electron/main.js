const { app, BrowserWindow, session, shell, Menu } = require('electron');
const path = require('path');

if (!app.requestSingleInstanceLock()) app.quit();
app.setAppUserModelId('com.feras.anasheed');

let win;
function create() {
  Menu.setApplicationMenu(null);
  win = new BrowserWindow({
    width: 1100, height: 820, minWidth: 380, minHeight: 500,
    backgroundColor: '#fbf6ec', title: 'أنشودتي',
    icon: path.join(__dirname, 'build', 'icon.ico'),
    webPreferences: { contextIsolation: true, sandbox: true },
  });
  const allow = ['media', 'screen-wake-lock', 'wakeLock', 'fullscreen'];
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(allow.includes(perm)));
  session.defaultSession.setPermissionCheckHandler((wc, perm) => allow.includes(perm));
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
  win.loadFile(path.join(__dirname, 'app', 'index.html'));
  // CI smoke test: ANASHEED_SMOKE=<file> → write page facts there and quit
  if (process.env.ANASHEED_SMOKE) {
    const out = process.env.ANASHEED_SMOKE, fs = require('fs');
    fs.writeFileSync(out, JSON.stringify({ stage: 'window created' }));
    win.webContents.on('did-fail-load', (e, code, desc, url) => fs.writeFileSync(out, JSON.stringify({ stage: 'did-fail-load', code, desc, url })));
    win.webContents.on('render-process-gone', (e, d) => fs.writeFileSync(out, JSON.stringify({ stage: 'renderer gone', d })));
    win.webContents.on('console-message', (e, level, msg) => { if (level >= 3) fs.appendFileSync(out + '.log', msg + '\n'); });
    win.webContents.on('did-finish-load', async () => { try {
      await new Promise(r => setTimeout(r, 1500));
      const facts = await win.webContents.executeJavaScript(`(async()=>({
        cards: document.querySelectorAll('#grid .card').length,
        secure: window.isSecureContext, mic: !!(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia),
        recorder: typeof MediaRecorder!=='undefined', idb: await dbReady.then(()=>!!db),
        amiri: document.fonts.check('24px Amiri'), version: VERSION }))()`);
      fs.writeFileSync(out, JSON.stringify(facts));
      } catch (err) { fs.writeFileSync(out, JSON.stringify({ stage: 'js error', err: String(err) })); }
      app.exit(0);
    });
  }
}
app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
app.whenReady().then(create);
app.on('window-all-closed', () => app.quit());
