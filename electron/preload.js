const { contextBridge, ipcRenderer } = require('electron');

// Expose safe, selected Electron APIs to the React application renderer
contextBridge.exposeInMainWorld('electronAPI', {
  sendEmergencyKill: () => ipcRenderer.send('emergency-kill'),
  onBackendStatus: (callback) => ipcRenderer.on('backend-status', (_event, value) => callback(value))
});
