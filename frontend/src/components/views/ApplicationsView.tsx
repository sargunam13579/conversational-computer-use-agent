import React, { useState } from 'react';
import { AppWindow, Play, Search, CheckCircle, Terminal } from 'lucide-react';
import { GlassCard } from '../common/GlassCard';
import { useNexus } from '../../context/NexusContext';
import { api } from '../../services/api';

interface AppItem {
  id: string;
  name: string;
  category: string;
  icon?: string;
  command: string;
}

export const ApplicationsView: React.FC = () => {
  const { addActivity } = useNexus();
  const [searchQuery, setSearchQuery] = useState('');
  const [runningApp, setRunningApp] = useState<string | null>(null);
  const [launchFeedback, setLaunchFeedback] = useState<string | null>(null);

  const defaultApps: AppItem[] = [
    { id: '1', name: 'Google Chrome / Chromium', category: 'Browser', command: 'chrome' },
    { id: '2', name: 'Visual Studio Code', category: 'Development', command: 'code' },
    { id: '3', name: 'Windows Terminal / PowerShell', category: 'System', command: 'powershell' },
    { id: '4', name: 'File Explorer', category: 'Utilities', command: 'explorer' },
    { id: '5', name: 'Notepad', category: 'Editor', command: 'notepad' },
    { id: '6', name: 'Task Manager', category: 'Diagnostics', command: 'taskmgr' },
    { id: '7', name: 'Calculator', category: 'Utilities', command: 'calc' },
    { id: '8', name: 'System Settings', category: 'System', command: 'ms-settings:' },
  ];

  const handleLaunch = async (app: AppItem) => {
    setRunningApp(app.name);
    setLaunchFeedback(null);
    try {
      addActivity({
        type: 'tool_exec',
        title: `Launching ${app.name}`,
        detail: `Attempting open_application with app_name: '${app.command}'`,
        status: 'info',
      });

      const res = await api.executeLaptopTool(
        'open_application',
        { app_name: app.command },
        true
      );

      setLaunchFeedback(res.output || `Application '${app.name}' launched successfully.`);
      addActivity({
        type: 'tool_exec',
        title: `${app.name} Launched`,
        detail: res.output || 'Application process started',
        status: res.success ? 'success' : 'warning',
      });
    } catch (err: any) {
      setLaunchFeedback(`Failed to launch ${app.name}: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setRunningApp(null);
    }
  };

  const filtered = defaultApps.filter((a) =>
    a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-display font-black text-xl text-white tracking-wider flex items-center gap-2">
            <AppWindow className="w-5 h-5 text-cyan-400" />
            APPLICATION LAUNCHER & REGISTRY
          </h2>
          <p className="font-tech text-xs text-slate-400 uppercase tracking-widest mt-1">
            Desktop Process Orchestration via open_application / switch_application
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search applications..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-xs font-sans text-white focus:outline-none focus:border-cyan-400"
          />
        </div>
      </div>

      {launchFeedback && (
        <div className="p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-mono text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>{launchFeedback}</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {filtered.map((app) => (
          <GlassCard key={app.id} className="p-4 flex flex-col justify-between space-y-4 group">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-tech text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 uppercase tracking-wider">
                  {app.category}
                </span>
                <Terminal className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 transition-colors" />
              </div>

              <h4 className="font-tech font-bold text-base text-white group-hover:text-cyan-200">
                {app.name}
              </h4>
              <p className="font-mono text-[11px] text-slate-400 truncate">
                cmd: {app.command}
              </p>
            </div>

            <button
              type="button"
              disabled={runningApp === app.name}
              onClick={() => handleLaunch(app)}
              className="cyber-btn w-full justify-center text-xs py-2"
            >
              <Play className="w-3.5 h-3.5" />
              {runningApp === app.name ? 'Launching...' : 'Launch Process'}
            </button>
          </GlassCard>
        ))}
      </div>
    </div>
  );
};
