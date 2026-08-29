const { app, BrowserWindow, Tray, Menu, globalShortcut } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let tray = null;
let backendProcess = null;
let isQuitting = false;

// Check if an instance of the backend is already running on port 8000
function checkBackendRunning(callback) {
  const req = http.request({ host: '127.0.0.1', port: 8000, path: '/api/health', method: 'GET', timeout: 1000 }, (res) => {
    callback(res.statusCode === 200);
  });
  req.on('error', () => {
    callback(false);
  });
  req.end();
}

// Spawns the Python FastAPI backend
function spawnBackend() {
  checkBackendRunning((running) => {
    if (running) {
      console.log('Backend is already running on port 8000.');
      return;
    }

    console.log('Starting backend server...');
    const isPackaged = app.isPackaged;
    let backendPath;
    let args = [];

    if (!isPackaged) {
      // In development, spawn the virtual env python entrypoint
      backendPath = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
      args = ['-m', 'nexus.main', '--mode', 'api'];
    } else {
      // In production, run the bundled executable
      backendPath = path.join(process.resourcesPath, 'backend', 'nexus_backend.exe');
    }

    try {
      backendProcess = spawn(backendPath, args, {
        cwd: path.join(__dirname, '..'),
        stdio: 'inherit',
        shell: true
      });

      backendProcess.on('error', (err) => {
        console.error('Failed to start backend process:', err);
      });
    } catch (err) {
      console.error('Error spawning backend:', err);
    }
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'Nexus AI',
    icon: path.join(__dirname, '..', 'frontend', 'public', 'vite.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  const isDev = !app.isPackaged;

  if (isDev) {
    mainWindow.loadURL('http://127.0.0.1:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'));
  }

  // Intercept the close event to hide to system tray instead of exiting
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  const iconPath = path.join(__dirname, '..', 'frontend', 'public', 'vite.svg');
  tray = new Tray(iconPath);
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open Nexus AI',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('Nexus AI');
  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// Register global keyboard shortcut controls
function registerShortcuts() {
  // Global shortcut to summon / toggle window visibility
  globalShortcut.register('Ctrl+Shift+N', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });

  // Global emergency kill switch shortcut (Ctrl+Shift+K)
  globalShortcut.register('Ctrl+Shift+K', () => {
    console.log('Emergency kill shortcut triggered');
    // Call the cancel / kill backend endpoint
    const req = http.request({ host: '127.0.0.1', port: 8000, path: '/api/identity/cancel', method: 'POST' });
    req.on('error', (err) => console.error('Kill request error:', err));
    req.end();
  });
}

app.whenReady().then(() => {
  spawnBackend();
  createWindow();
  createTray();
  registerShortcuts();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('will-quit', () => {
  // Unregister all shortcuts
  globalShortcut.unregisterAll();

  // Terminate Python backend on shutdown
  if (backendProcess) {
    console.log('Terminating Python backend server process...');
    try {
      process.kill(-backendProcess.pid); // Kill process group if supported
    } catch {
      backendProcess.kill();
    }
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
