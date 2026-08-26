import React, { useState, useEffect } from 'react';
import {
  Sliders,
  Volume2,
  VolumeX,
  Lock,
  Camera,
  Cpu,
  Terminal,
  Play,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  HardDrive,
  Monitor,
} from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { GlassCard } from '../common/GlassCard';
import { StatusBadge } from '../common/StatusBadge';
import { api } from '../../services/api';
import type { LaptopToolSchema, ToolExecutionResponse } from '../../types';

export const SystemControlView: React.FC = () => {
  const { laptopStatus, refreshState, addActivity } = useNexus();
  const [tools, setTools] = useState<LaptopToolSchema[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>('get_system_info');
  const [toolParams, setToolParams] = useState<string>('{}');
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<ToolExecutionResponse | null>(null);

  // Volume slider state
  const [volumeLevel, setVolumeLevel] = useState<number>(50);
  const [volumeFeedback, setVolumeFeedback] = useState<string | null>(null);

  useEffect(() => {
    api
      .listLaptopTools()
      .then((res) => {
        setTools(res.tools || []);
      })
      .catch((err) => console.warn('Could not load tool catalog:', err));
  }, []);

  const handleRunTool = async (name: string, rawParams: string) => {
    setIsExecuting(true);
    setExecutionResult(null);

    let parsed: Record<string, unknown> = {};
    try {
      if (rawParams.trim()) {
        parsed = JSON.parse(rawParams);
      }
    } catch {
      alert('Invalid JSON parameters format');
      setIsExecuting(false);
      return;
    }

    try {
      addActivity({
        type: 'tool_exec',
        title: `Dispatching ${name}`,
        detail: `Calling /api/laptop/execute with payload`,
        status: 'info',
      });

      const res = await api.executeLaptopTool(name, parsed, true);
      setExecutionResult(res);

      addActivity({
        type: 'tool_exec',
        title: `${name} Result`,
        detail: res.output || JSON.stringify(res.data) || 'Execution completed',
        status: res.success ? 'success' : 'error',
      });
      refreshState();
    } catch (err: any) {
      setExecutionResult({
        request_id: `err_${Date.now()}`,
        tool_name: name,
        success: false,
        output: '',
        data: {},
        error: err?.response?.data?.detail || err.message,
        duration_seconds: 0,
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const handleSetVolume = async (newVol: number) => {
    setVolumeLevel(newVol);
    try {
      const res = await api.executeLaptopTool('set_volume', { level: newVol }, true);
      setVolumeFeedback(res.output || `Volume adjusted to ${newVol}%`);
      setTimeout(() => setVolumeFeedback(null), 3000);
    } catch (err: any) {
      setVolumeFeedback('Volume control failed');
    }
  };

  const handleMuteToggle = async () => {
    try {
      const res = await api.executeLaptopTool('volume_control', { action: 'mute' }, true);
      setVolumeFeedback(res.output || 'Toggled audio mute');
      setTimeout(() => setVolumeFeedback(null), 3000);
    } catch (err: any) {
      setVolumeFeedback('Mute toggle failed');
    }
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-8">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="font-display font-black text-xl text-white tracking-wider flex items-center gap-2">
            <Sliders className="w-5 h-5 text-cyan-400" />
            SYSTEM CONTROL CENTER
          </h2>
          <p className="font-tech text-xs text-slate-400 uppercase tracking-widest mt-1">
            Local Workstation Telemetry & Authorized OS Tool Orchestration
          </p>
        </div>

        <button
          type="button"
          onClick={() => refreshState()}
          className="cyber-btn text-xs px-3 py-1.5 self-start"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Diagnostics
        </button>
      </div>

      {/* Diagnostics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlassCard className="p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-tech text-slate-400">
            <span>HOST PLATFORM</span>
            <Monitor className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="font-tech font-bold text-base text-white">
            {laptopStatus?.hostname || 'WINDOWS-NODE'}
          </div>
          <div className="font-mono text-xs text-cyan-300">
            {laptopStatus?.os || 'Windows'} {laptopStatus?.os_version || '11'}
          </div>
        </GlassCard>

        <GlassCard className="p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-tech text-slate-400">
            <span>CPU & MEMORY LOAD</span>
            <Cpu className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-center gap-3">
            <div>
              <div className="font-tech text-[10px] text-slate-400">CPU</div>
              <div className="font-display font-bold text-base text-purple-300">
                {laptopStatus?.cpu_percent != null ? `${laptopStatus.cpu_percent}%` : 'NOMINAL'}
              </div>
            </div>
            <div className="h-6 w-px bg-slate-800" />
            <div>
              <div className="font-tech text-[10px] text-slate-400">RAM</div>
              <div className="font-display font-bold text-base text-cyan-300">
                {laptopStatus?.memory_percent != null ? `${laptopStatus.memory_percent}%` : 'NOMINAL'}
              </div>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-tech text-slate-400">
            <span>NETWORK ADDRESS</span>
            <HardDrive className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="font-tech font-bold text-base text-white">
            {laptopStatus?.ip_address || '127.0.0.1'}
          </div>
          <div className="font-tech text-xs text-emerald-400 flex items-center gap-1">
            <StatusBadge status="online" label="LOCAL AGENT BOUND" size="sm" />
          </div>
        </GlassCard>
      </div>

      {/* Control Dials & Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Action Panels */}
        <div className="space-y-4">
          <h3 className="font-display font-bold text-sm text-white tracking-wider">
            QUICK HARDWARE DIRECTIVES
          </h3>

          {/* Volume Control Card */}
          <GlassCard className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Volume2 className="w-4 h-4 text-cyan-400" />
                <span className="font-tech font-bold text-sm text-white">
                  AUDIO MASTER OUTPUT
                </span>
              </div>
              <span className="font-mono text-xs text-cyan-300 font-bold">
                {volumeLevel}%
              </span>
            </div>

            <input
              type="range"
              min="0"
              max="100"
              value={volumeLevel}
              onChange={(e) => handleSetVolume(Number(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer bg-slate-800 h-1.5 rounded-lg"
            />

            <div className="flex items-center justify-between gap-2 pt-1">
              <button
                type="button"
                onClick={handleMuteToggle}
                className="cyber-btn text-xs px-3 py-1.5 flex items-center gap-1.5"
              >
                <VolumeX className="w-3.5 h-3.5" />
                Toggle Mute
              </button>

              <button
                type="button"
                onClick={() => handleSetVolume(20)}
                className="cyber-btn text-xs px-2.5 py-1.5"
              >
                20%
              </button>

              <button
                type="button"
                onClick={() => handleSetVolume(70)}
                className="cyber-btn text-xs px-2.5 py-1.5"
              >
                70%
              </button>
            </div>

            {volumeFeedback && (
              <div className="font-tech text-xs text-cyan-300 bg-cyan-500/10 p-2 rounded border border-cyan-500/30">
                {volumeFeedback}
              </div>
            )}
          </GlassCard>

          {/* Screen & Privacy Card */}
          <GlassCard className="p-5 space-y-3">
            <span className="font-tech font-bold text-sm text-white flex items-center gap-2">
              <Lock className="w-4 h-4 text-rose-400" />
              PRIVACY & WORKSTATION STATE
            </span>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                onClick={() => handleRunTool('lock_screen', '{}')}
                className="cyber-btn cyber-btn-danger text-xs p-2.5 flex flex-col items-center justify-center gap-1 text-center"
              >
                <Lock className="w-4 h-4" />
                <span>Lock Screen</span>
              </button>

              <button
                type="button"
                onClick={() => handleRunTool('screenshot', '{"action": "capture"}')}
                className="cyber-btn text-xs p-2.5 flex flex-col items-center justify-center gap-1 text-center"
              >
                <Camera className="w-4 h-4" />
                <span>Screenshot</span>
              </button>
            </div>
          </GlassCard>
        </div>

        {/* Right Tool Execution Console (2 Columns) */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="font-display font-bold text-sm text-white tracking-wider flex items-center gap-2">
            <Terminal className="w-4 h-4 text-cyan-400" />
            DIRECT TOOL RUNNER & DISPATCHER
          </h3>

          <GlassCard glow corners className="p-5 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-tech text-xs text-slate-400 uppercase mb-1.5">
                  Select Registered Tool ({tools.length})
                </label>
                <select
                  value={selectedTool}
                  onChange={(e) => setSelectedTool(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-400"
                >
                  {tools.map((t) => (
                    <option key={t.name} value={t.name}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-tech text-xs text-slate-400 uppercase mb-1.5">
                  Parameters (JSON)
                </label>
                <input
                  type="text"
                  value={toolParams}
                  onChange={(e) => setToolParams(e.target.value)}
                  placeholder='{"param": "value"}'
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-400"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <div className="font-sans text-xs text-slate-400 max-w-md truncate">
                {tools.find((t) => t.name === selectedTool)?.description ||
                  'Execute authorized backend laptop action safely.'}
              </div>

              <button
                type="button"
                disabled={isExecuting}
                onClick={() => handleRunTool(selectedTool, toolParams)}
                className="cyber-btn cyber-btn-primary px-5 py-2 text-xs"
              >
                <Play className="w-3.5 h-3.5" />
                {isExecuting ? 'Executing...' : 'Dispatch Tool'}
              </button>
            </div>

            {/* Output Result Viewer */}
            {executionResult && (
              <div className="mt-4 p-4 rounded-lg bg-slate-950/90 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-tech">
                  <div className="flex items-center gap-1.5">
                    {executionResult.success ? (
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-rose-400" />
                    )}
                    <span className="font-bold text-white uppercase">
                      {executionResult.tool_name} Result
                    </span>
                  </div>
                  <span className="font-mono text-slate-400">
                    {executionResult.duration_seconds}s
                  </span>
                </div>

                {executionResult.output && (
                  <pre className="p-3 rounded bg-slate-900 font-mono text-xs text-cyan-200 overflow-x-auto whitespace-pre-wrap max-h-48">
                    {executionResult.output}
                  </pre>
                )}

                {executionResult.error && (
                  <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 font-mono text-xs">
                    {executionResult.error}
                  </div>
                )}
              </div>
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
};
