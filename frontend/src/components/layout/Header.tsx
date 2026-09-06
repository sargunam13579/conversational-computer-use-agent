import React, { useState, useEffect } from 'react';
import { Power, Activity, ArrowLeft } from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { useVoice } from '../../context/VoiceContext';
import { SoundWaveVisualizer } from '../common/SoundWaveVisualizer';
import { api } from '../../services/api';
import appLogo from '../../assets/app-logo.png';

export const Header: React.FC = () => {
  const {
    identity,
    health,
    triggerEmergencyStop,
    setIsComputerUseActive,
  } = useNexus();
  const { voiceState, stopSpeaking } = useVoice();
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

  const assistantName = identity?.assistant_name || 'Seyal AI';

  const handleBackToSimpleChat = () => {
    stopSpeaking();
    api.stopComputerUse().catch(() => {});
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsComputerUseActive(false);
  };

  return (
    <header className="glass-panel rounded-none border-t-0 border-x-0 border-b border-cyan-500/20 px-5 py-2.5 flex items-center justify-between z-30 sticky top-0 bg-slate-950/85 backdrop-blur-xl">

      {/* LEFT — Brand + Assistant Name + AI Model */}
      <div className="flex items-center gap-3 shrink-0">
        <h1 className="font-display font-black text-2xl tracking-wider text-white leading-none">
          Seyal <span className="text-cyan-400">AI</span>
        </h1>
        <span className="text-slate-600 font-mono text-sm">|</span>
        <span className="font-tech text-sm tracking-wider text-cyan-300 font-semibold uppercase">
          {assistantName} CORE
        </span>
        {health?.llm_providers?.length ? (
          <span className="hidden sm:inline-flex items-center gap-1 text-xs font-tech text-emerald-400 font-semibold uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {health.llm_providers.join(', ').toUpperCase()} ACTIVE
          </span>
        ) : null}
      </div>

      {/* CENTER — Animated Sound Wave + Voice Status */}
      <div className="hidden lg:flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-slate-900/60 border border-slate-800">
        <Activity className="w-4 h-4 text-cyan-400 shrink-0" />
        <SoundWaveVisualizer state={voiceState} barCount={10} />
        <span className="font-tech text-xs font-semibold uppercase tracking-wider text-slate-300 whitespace-nowrap">
          VOICE: <span className="text-cyan-400">{voiceState}</span>
        </span>
      </div>

      {/* RIGHT — Clock · Kill Switch · Back · Logo */}
      <div className="flex items-center gap-3 shrink-0">

        {/* Clock + Date */}
        <div className="text-right hidden md:block">
          <div className="font-mono font-bold text-sm text-cyan-200 tracking-wider leading-tight">
            {timeStr || '00:00:00'}
          </div>
          <div className="font-tech text-[9px] text-slate-500 tracking-widest">
            {dateStr || ''}
          </div>
        </div>

        {/* Divider */}
        <span className="hidden md:block w-px h-7 bg-slate-800" />

        {/* KILL SWITCH */}
        <button
          type="button"
          onClick={triggerEmergencyStop}
          className="cyber-btn cyber-btn-danger px-3 py-1.5 text-xs font-tech font-bold flex items-center gap-1.5 shrink-0"
          title="Universal Kill Switch — Emergency Stop All Autonomous Actions"
        >
          <Power className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">KILL SWITCH</span>
        </button>

        {/* Back to Simple Chat */}
        <button
          onClick={handleBackToSimpleChat}
          title="Return to Simple Chatbot"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-700/70 hover:border-cyan-500/50 hover:bg-slate-800/80 text-slate-300 hover:text-cyan-300 transition-all text-xs font-medium group shrink-0"
        >
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          <span className="hidden sm:inline whitespace-nowrap">Back to Simple Chat</span>
        </button>

        {/* Conversational Computer Use Agent Logo */}
        <div
          className="relative shrink-0"
          title="Conversational Computer-Use Agent Active"
        >
          <div className="w-9 h-9 rounded-full overflow-hidden border-2 border-cyan-400/60 shadow-[0_0_14px_rgba(0,240,255,0.5)] bg-slate-950">
            <img
              src={appLogo}
              alt="Seyal AI Agent"
              className="w-full h-full object-cover rounded-full"
            />
          </div>
          {/* Active glow badge */}
          <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-cyan-400 border-2 border-slate-950 animate-ping" />
          <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-cyan-400 border-2 border-slate-950" />
        </div>

      </div>
    </header>
  );
};
