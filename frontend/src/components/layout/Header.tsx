import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Database,
  Radio,
  Power,
  Activity,
} from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { useVoice } from '../../context/VoiceContext';
import { StatusBadge } from '../common/StatusBadge';
import { SoundWaveVisualizer } from '../common/SoundWaveVisualizer';

export const Header: React.FC = () => {
  const { identity, health, isBackendConnected, triggerEmergencyStop } = useNexus();
  const { voiceState } = useVoice();
  const [timeStr, setTimeStr] = useState<string>('');
  const [dateStr, setDateStr] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
      setDateStr(
        now.toLocaleDateString('en-US', {
          weekday: 'short',
          month: 'short',
          day: '2-digit',
          year: 'numeric',
        }).toUpperCase()
      );
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds?: number) => {
    if (!seconds) return '00:00:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const assistantName = identity?.assistant_name || 'NEXUS';

  return (
    <header className="glass-panel rounded-none border-t-0 border-x-0 border-b border-cyan-500/20 px-6 py-3.5 flex items-center justify-between z-30 sticky top-0 bg-slate-950/80 backdrop-blur-xl">
      {/* Brand & Assistant Identity */}
      <div className="flex items-center gap-4">
        <div className="relative flex items-center justify-center">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-400/40 flex items-center justify-center shadow-[0_0_15px_rgba(0,240,255,0.25)]">
            <Radio className="w-5 h-5 text-cyan-400 animate-pulse" />
          </div>
          <span className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-emerald-500 border-2 border-slate-950" />
        </div>

        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="font-display font-black text-xl tracking-wider text-white">
              NEXUS
            </h1>
            <span className="text-xs px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-tech font-bold tracking-widest border border-cyan-500/30">
              v{health?.version || '0.1.0'}
            </span>
            <span className="text-xs text-slate-500 font-mono">|</span>
            <span className="font-tech text-sm tracking-wider text-cyan-300 font-semibold uppercase glow-text-cyan">
              {assistantName} CORE
            </span>
          </div>
          <p className="font-tech text-xs tracking-wider text-slate-400 flex items-center gap-2">
            <span>OPERATIONAL OS</span>
            <span>•</span>
            <span className="text-emerald-400">
              {health?.llm_providers?.length ? `${health.llm_providers.join(', ').toUpperCase()} ACTIVE` : 'LOCAL ENGINE'}
            </span>
          </p>
        </div>
      </div>

      {/* Center Soundwave & Voice status indicator */}
      <div className="hidden lg:flex items-center gap-3 px-4 py-1.5 rounded-full bg-slate-900/60 border border-slate-800">
        <Activity className="w-4 h-4 text-cyan-400" />
        <SoundWaveVisualizer state={voiceState} barCount={10} />
        <span className="font-tech text-xs font-semibold uppercase tracking-wider text-slate-300">
          VOICE: <span className="text-cyan-400">{voiceState}</span>
        </span>
      </div>

      {/* Right Telemetry & Emergency Controls */}
      <div className="flex items-center gap-5">
        {/* Clock */}
        <div className="text-right hidden sm:block">
          <div className="font-mono font-bold text-base text-cyan-200 tracking-wider">
            {timeStr || '00:00:00'}
          </div>
          <div className="font-tech text-[10px] text-slate-400 tracking-widest">
            {dateStr || 'NEXUS TIME'}
          </div>
        </div>

        {/* Backend & DB status */}
        <div className="hidden md:flex items-center gap-3 pl-3 border-l border-slate-800">
          <div className="flex items-center gap-1.5 text-xs font-tech text-slate-300" title="Database Connection">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-mono text-[11px] text-emerald-400 uppercase">
              {health?.database_status === 'connected' ? 'DB:OK' : 'DB:READY'}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-xs font-tech text-slate-300" title="System Uptime">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span className="font-mono text-[11px] text-purple-300">
              UP: {formatUptime(health?.uptime_seconds)}
            </span>
          </div>

          <StatusBadge
            status={isBackendConnected ? 'online' : 'offline'}
            label={isBackendConnected ? 'API LINK' : 'OFFLINE'}
            size="sm"
          />
        </div>

        {/* Emergency Stop / Kill switch */}
        <button
          type="button"
          onClick={triggerEmergencyStop}
          className="cyber-btn cyber-btn-danger px-3 py-1.5 text-xs font-tech font-bold flex items-center gap-1.5"
          title="Universal Kill Switch - Emergency Stop All Autonomous Actions"
        >
          <Power className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">KILL SWITCH</span>
        </button>
      </div>
    </header>
  );
};
