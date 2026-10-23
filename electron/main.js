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
    win.webContents.on('did-finish-load', async () => {
      await new Promise(r => setTimeout(r, 1500));
      const facts = await win.webContents.executeJavaScript(`(async()=>({
        cards: document.querySelectorAll('#grid .card').length,
        secure: window.isSecureContext, mic: !!(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia),
        recorder: typeof MediaRecorder!=='undefined', idb: await dbReady.then(()=>!!db),
        amiri: document.fonts.check('24px Amiri'), version: VERSION }))()`);
      require('fs').writeFileSync(process.env.ANASHEED_SMOKE, JSON.stringify(facts));
      app.exit(0);
    });
  }
}
app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
app.whenReady().then(create);
app.on('window-all-closed', () => app.quit());
