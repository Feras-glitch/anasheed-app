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
}
app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
app.whenReady().then(create);
app.on('window-all-closed', () => app.quit());
