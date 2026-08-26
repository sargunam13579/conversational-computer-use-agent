import React from 'react';
import {
  Activity,
  Cpu,
  HardDrive,
  Layers,
  Terminal,
  Volume2,
  Lock,
  Camera,
  MessageSquare,
  Sparkles,
  Zap,
  ArrowUpRight,
  ShieldCheck,
  Smartphone,
} from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { useVoice } from '../../context/VoiceContext';
import { GlassCard } from '../common/GlassCard';
import { StatusBadge } from '../common/StatusBadge';
import { HolographicOrb } from '../common/HolographicOrb';
import { api } from '../../services/api';

export const DashboardView: React.FC = () => {
  const { identity, health, laptopStatus, setActiveView, addActivity } = useNexus();
  const { voiceState } = useVoice();

  const handleQuickTool = async (toolName: string, params: Record<string, unknown> = {}, title: string) => {
    try {
      addActivity({
        type: 'tool_exec',
        title: `Invoking ${title}`,
        detail: `Executing tool '${toolName}' from Quick Actions`,
        status: 'info',
      });
      const res = await api.executeLaptopTool(toolName, params, true);
      addActivity({
        type: 'tool_exec',
        title: `${title} Output`,
        detail: res.output || JSON.stringify(res.data) || 'Action completed successfully',
        status: res.success ? 'success' : 'error',
      });
    } catch (err: any) {
      addActivity({
        type: 'tool_exec',
        title: `${title} Failed`,
        detail: err?.response?.data?.detail || err.message,
        status: 'error',
      });
    }
  };

  const assistantName = identity?.assistant_name || 'JARVIS';
  const userName = identity?.user_name && identity.user_name !== 'User' ? identity.user_name : 'Sargunam';

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* Hero HUD Greeting Card */}
      <GlassCard glow corners className="p-5 md:p-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="space-y-3 text-center md:text-left flex-1">
            <div className="flex flex-wrap items-center justify-center md:justify-start gap-2">
              <span className="font-tech text-xs uppercase px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-semibold">
                SYSTEM ONLINE
              </span>
              <StatusBadge status="online" label="ALWAYS-LIVE CALL READY" size="sm" />
            </div>

            <h2 className="font-display font-black text-2xl lg:text-3xl tracking-wide text-white">
              GREETINGS, <span className="glow-text-cyan">{userName.toUpperCase()}</span>
            </h2>

            <p className="font-sans text-sm text-slate-300 max-w-2xl leading-relaxed">
              I am <strong className="text-cyan-300 font-tech uppercase">{assistantName}</strong>, your always-live AI companion. 
              Standing by for natural hands-free voice conversation, workflow automation, and workstation orchestration.
            </p>

            <div className="flex flex-wrap items-center justify-center md:justify-start gap-3 pt-2">
              <button
                type="button"
                onClick={() => setActiveView('assistant')}
                className="cyber-btn cyber-btn-primary px-5 py-2.5"
              >
                <MessageSquare className="w-4 h-4" />
                Live Conversation
              </button>

              <button
                type="button"
                onClick={() => {
                  setActiveView('assistant');
                }}
                className="cyber-btn px-5 py-2.5"
              >
                <Sparkles className="w-4 h-4 text-cyan-400" />
                Live Voice Mode
              </button>

              <button
                type="button"
                onClick={() => setActiveView('system')}
                className="cyber-btn text-slate-300 hover:text-white px-4 py-2.5"
              >
                <Terminal className="w-4 h-4 text-purple-400" />
                System Control
              </button>
            </div>
          </div>

          {/* Central AI Holographic Core */}
          <div className="shrink-0 flex flex-col items-center justify-center p-2">
            <HolographicOrb
              state={voiceState}
              size={150}
              label={`${assistantName} AI CORE`}
              onClick={() => setActiveView('assistant')}
            />
          </div>
        </div>
      </GlassCard>

      {/* 4-Column System Telemetry Status Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <GlassCard className="p-4 flex items-center gap-3.5">
          <div className="p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-400/30 text-cyan-400 shrink-0">
            <Activity className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="font-tech text-xs text-slate-400 uppercase tracking-wider truncate">
              LLM Brain Engine
            </div>
            <div className="font-display font-bold text-base text-white truncate">
              {health?.llm_providers?.length ? health.llm_providers[0].toUpperCase() : 'ONLINE'}
            </div>
            <div className="font-tech text-[11px] text-emerald-400 flex items-center gap-1 mt-0.5">
              <Zap className="w-3 h-3" />
              {health?.llm_providers?.length || 1} Provider Active
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4 flex items-center gap-3.5">
          <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-400/30 text-purple-400 shrink-0">
            <Cpu className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="font-tech text-xs text-slate-400 uppercase tracking-wider truncate">
              CPU Utilization
            </div>
            <div className="font-display font-bold text-base text-white">
              {laptopStatus?.cpu_percent != null ? `${laptopStatus.cpu_percent}%` : 'NOMINAL'}
            </div>
            <div className="font-tech text-[11px] text-purple-300 mt-0.5 truncate">
              Host: {laptopStatus?.hostname || 'WINDOWS-HOST'}
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4 flex items-center gap-3.5">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-400/30 text-emerald-400 shrink-0">
            <Layers className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="font-tech text-xs text-slate-400 uppercase tracking-wider truncate">
              Active Tool Registry
            </div>
            <div className="font-display font-bold text-base text-white">
              {health?.tool_count || 67} TOOLS
            </div>
            <div className="font-tech text-[11px] text-emerald-400 mt-0.5 truncate">
              Full OS Permission Guard
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4 flex items-center gap-3.5">
          <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-400/30 text-amber-400 shrink-0">
            <HardDrive className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="font-tech text-xs text-slate-400 uppercase tracking-wider truncate">
              System Memory / DB
            </div>
            <div className="font-display font-bold text-base text-white truncate">
              {laptopStatus?.memory_percent != null ? `${laptopStatus.memory_percent}% RAM` : 'SQLITE READY'}
            </div>
            <div className="font-tech text-[11px] text-amber-300 mt-0.5 truncate">
              Persistent Memory Active
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Main Grid: Quick Action Matrix (2 Cols) + Connected Nodes (1 Col) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Quick Action Cards (2 Columns) */}
        <div className="lg:col-span-2 space-y-3.5">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-bold text-sm text-white tracking-wider flex items-center gap-2">
              <Zap className="w-4 h-4 text-cyan-400" />
              QUICK COMMAND ACTION MATRIX
            </h3>
            <span className="font-tech text-xs text-slate-400">Authorized Workstation Controls</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <GlassCard
              onClick={() => handleQuickTool('get_system_info', {}, 'System Diagnostics')}
              className="p-4 group border-slate-800 hover:border-cyan-400/50"
            >
              <div className="flex items-start justify-between">
                <div className="p-2 rounded bg-cyan-500/10 text-cyan-400 group-hover:bg-cyan-500/20">
                  <Terminal className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-300 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
              <h4 className="font-tech font-bold text-sm text-white mt-2.5 group-hover:text-cyan-200">
                System Diagnostics
              </h4>
              <p className="font-sans text-xs text-slate-400 mt-1">
                Query host OS architecture, hardware load, and running processes.
              </p>
            </GlassCard>

            <GlassCard
              onClick={() => handleQuickTool('screenshot', { action: 'capture' }, 'Screen Capture')}
              className="p-4 group border-slate-800 hover:border-purple-400/50"
            >
              <div className="flex items-start justify-between">
                <div className="p-2 rounded bg-purple-500/10 text-purple-400 group-hover:bg-purple-500/20">
                  <Camera className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-purple-300 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
              <h4 className="font-tech font-bold text-sm text-white mt-2.5 group-hover:text-purple-200">
                Take Desktop Screenshot
              </h4>
              <p className="font-sans text-xs text-slate-400 mt-1">
                Capture screen view for AI vision analysis or snapshot archives.
              </p>
            </GlassCard>

            <GlassCard
              onClick={() => handleQuickTool('volume_control', { action: 'get' }, 'Volume State')}
              className="p-4 group border-slate-800 hover:border-emerald-400/50"
            >
              <div className="flex items-start justify-between">
                <div className="p-2 rounded bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20">
                  <Volume2 className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-300 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
              <h4 className="font-tech font-bold text-sm text-white mt-2.5 group-hover:text-emerald-200">
                Check Audio Levels
              </h4>
              <p className="font-sans text-xs text-slate-400 mt-1">
                Inspect master audio output volume and mute status.
              </p>
            </GlassCard>

            <GlassCard
              onClick={() => handleQuickTool('lock_screen', {}, 'Lock Screen')}
              className="p-4 group border-slate-800 hover:border-rose-400/50"
            >
              <div className="flex items-start justify-between">
                <div className="p-2 rounded bg-rose-500/10 text-rose-400 group-hover:bg-rose-500/20">
                  <Lock className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-rose-300 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
              <h4 className="font-tech font-bold text-sm text-white mt-2.5 group-hover:text-rose-200">
                Security Lock Host
              </h4>
              <p className="font-sans text-xs text-slate-400 mt-1">
                Instantly trigger workstation lock screen for operator privacy.
              </p>
            </GlassCard>
          </div>
        </div>

        {/* Connected Ecosystem Status Panel (1 Column) */}
        <div className="space-y-3.5">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-bold text-sm text-white tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-400" />
              DEVICE ECOSYSTEM
            </h3>
            <button
              type="button"
              onClick={() => setActiveView('devices')}
              className="text-xs font-tech text-cyan-400 hover:underline uppercase"
            >
              Manage Mesh
            </button>
          </div>

          <GlassCard className="p-4 space-y-3">
            <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#10b981]" />
                <div>
                  <div className="font-tech font-bold text-sm text-white">
                    {laptopStatus?.hostname || 'Host Workstation'}
                  </div>
                  <div className="font-mono text-[11px] text-slate-400">
                    {laptopStatus?.os || 'Windows 11'} • {laptopStatus?.ip_address || '127.0.0.1'}
                  </div>
                </div>
              </div>
              <StatusBadge status="online" label="HOST" size="sm" />
            </div>

            <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800 flex items-center justify-between opacity-80">
              <div className="flex items-center gap-2.5">
                <Smartphone className="w-4 h-4 text-purple-400" />
                <div>
                  <div className="font-tech font-bold text-sm text-slate-300">
                    Android Companion Node
                  </div>
                  <div className="font-mono text-[11px] text-slate-500">
                    ADB / TCP Mesh Ready
                  </div>
                </div>
              </div>
              <StatusBadge status="idle" label="STANDBY" size="sm" />
            </div>

            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-tech text-slate-400">
              <span>WAKE WORD:</span>
              <span className="font-mono text-cyan-300 font-semibold">
                "{identity?.wake_word || 'hey nexus'}"
              </span>
            </div>

            <div className="flex items-center justify-between text-xs font-tech text-slate-400 pt-1">
              <span>SAFETY GUARD:</span>
              <span className="flex items-center gap-1 text-emerald-400 font-mono">
                <ShieldCheck className="w-3.5 h-3.5" /> ACTIVE
              </span>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
};
