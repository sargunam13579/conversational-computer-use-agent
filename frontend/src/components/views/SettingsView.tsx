import React, { useState, useEffect } from 'react';
import {
  Settings,
  Shield,
  Radio,
  Plus,
  Trash2,
  Save,
  Mic,
  Volume2,
} from 'lucide-react';
import { GlassCard } from '../common/GlassCard';
import { StatusBadge } from '../common/StatusBadge';
import { useNexus } from '../../context/NexusContext';
import { useVoice } from '../../context/VoiceContext';
import { api } from '../../services/api';
import type { VoiceStatusResponse } from '../../types';

export const SettingsView: React.FC = () => {
  const { identity, requestNameChange, refreshState, addActivity } = useNexus();
  const {
    autoVoiceResponse,
    setAutoVoiceResponse,
    selectedVoiceName,
    setSelectedVoiceName,
    availableVoices,
    testVoice,
  } = useVoice();

  // Assistant name state
  const [targetName, setTargetName] = useState('');
  const [nameChangeStatus, setNameChangeStatus] = useState<string | null>(null);
  const [isChangingName, setIsChangingName] = useState(false);

  // User name state
  const [userNameInput, setUserNameInput] = useState(identity?.user_name || '');

  // Alias state
  const [newAlias, setNewAlias] = useState('');
  const [isAddingAlias, setIsAddingAlias] = useState(false);

  // Voice settings state
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatusResponse | null>(null);
  const [voicePipelineActive, setVoicePipelineActive] = useState(false);
  const [isTestingVoice, setIsTestingVoice] = useState(false);

  useEffect(() => {
    if (identity) {
      setUserNameInput(identity.user_name || '');
    }
  }, [identity]);

  useEffect(() => {
    api
      .getVoiceStatus()
      .then((res) => {
        setVoiceStatus(res);
        setVoicePipelineActive(res.pipeline.running);
      })
      .catch((err) => console.warn('Could not load voice status:', err));
  }, []);

  const handleTestVoice = async () => {
    setIsTestingVoice(true);
    try {
      await testVoice();
    } finally {
      setTimeout(() => setIsTestingVoice(false), 2000);
    }
  };

  const handleNameChangeRequest = async () => {
    if (!targetName.trim()) return;
    setIsChangingName(true);
    setNameChangeStatus(null);

    try {
      const prompt = await requestNameChange(targetName.trim());
      setNameChangeStatus(prompt || `Confirmation requested to rename assistant to '${targetName}'`);
      setTargetName('');
    } catch (err: any) {
      setNameChangeStatus(`Error: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsChangingName(false);
    }
  };

  const handleUpdateUserName = async () => {
    try {
      await api.updateIdentity({ user_name: userNameInput.trim() });
      addActivity({
        type: 'identity',
        title: 'Operator Name Updated',
        detail: `User name updated to '${userNameInput}'`,
        status: 'success',
      });
      await refreshState();
    } catch (err: any) {
      alert(`Update failed: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleAddAlias = async () => {
    if (!newAlias.trim()) return;
    setIsAddingAlias(true);
    try {
      await api.addAlias(newAlias.trim());
      setNewAlias('');
      addActivity({
        type: 'identity',
        title: 'Wake Word Alias Added',
        detail: `Alias '${newAlias}' registered`,
        status: 'success',
      });
      await refreshState();
    } catch (err: any) {
      alert(`Add alias failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsAddingAlias(false);
    }
  };

  const handleRemoveAlias = async (alias: string) => {
    try {
      await api.removeAlias(alias);
      addActivity({
        type: 'identity',
        title: 'Wake Word Alias Removed',
        detail: `Alias '${alias}' revoked`,
        status: 'info',
      });
      await refreshState();
    } catch (err: any) {
      alert(`Remove alias failed: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleToggleVoicePipeline = async () => {
    try {
      if (voicePipelineActive) {
        await api.stopVoice();
        setVoicePipelineActive(false);
      } else {
        await api.startVoice();
        setVoicePipelineActive(true);
      }
      const updated = await api.getVoiceStatus();
      setVoiceStatus(updated);
    } catch (err: any) {
      alert(`Voice toggle failed: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const currentAssistantName = identity?.assistant_name || 'NEXUS';

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-8">
      <div>
        <h2 className="font-display font-black text-xl text-white tracking-wider flex items-center gap-2">
          <Settings className="w-5 h-5 text-cyan-400" />
          NEXUS IDENTITY & SYSTEM CONFIGURATION
        </h2>
        <p className="font-tech text-xs text-slate-400 uppercase tracking-widest mt-1">
          Assistant Persona, Two-Step Confirmation Guards, Wake Words & Audio Pipelines
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Assistant Identity & Name Change Flow */}
        <GlassCard glow corners className="p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <Shield className="w-5 h-5 text-cyan-400" />
              <h3 className="font-display font-bold text-sm text-white tracking-wider">
                ASSISTANT IDENTITY
              </h3>
            </div>
            <StatusBadge
              status={identity?.has_pending_confirmation ? 'warning' : 'online'}
              label={
                identity?.has_pending_confirmation
                  ? 'CONFIRMATION PENDING'
                  : 'IDENTITY SYNCHRONIZED'
              }
              size="sm"
            />
          </div>

          <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
            <span className="font-tech text-xs text-slate-400 uppercase">
              Current Active Name
            </span>
            <div className="font-display font-black text-2xl text-cyan-300 glow-text-cyan uppercase">
              {currentAssistantName}
            </div>
            <p className="font-sans text-xs text-slate-400 pt-1">
              Backend identity registered in <code className="text-cyan-400 font-mono">/api/identity</code>.
            </p>
          </div>

          {/* Name Change Input Form */}
          <div className="space-y-2 pt-1">
            <label className="block font-tech text-xs text-slate-300 uppercase font-semibold">
              Request Persona Name Change
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={targetName}
                onChange={(e) => setTargetName(e.target.value)}
                placeholder="e.g. Jarvis, Friday, Nova..."
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-400 font-sans"
              />
              <button
                type="button"
                disabled={!targetName.trim() || isChangingName}
                onClick={handleNameChangeRequest}
                className="cyber-btn cyber-btn-primary text-xs px-4"
              >
                {isChangingName ? 'Requesting...' : 'Initiate Change'}
              </button>
            </div>
            <p className="text-[11px] text-slate-400 font-sans">
              Initiates a 2-step verification. An authorization banner/modal will prompt for approval before applying.
            </p>
          </div>

          {nameChangeStatus && (
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-mono">
              {nameChangeStatus}
            </div>
          )}

          {/* User Operator Name */}
          <div className="pt-3 border-t border-slate-800 space-y-2">
            <label className="block font-tech text-xs text-slate-300 uppercase font-semibold">
              Operator Designation (User Name)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={userNameInput}
                onChange={(e) => setUserNameInput(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-400 font-sans"
              />
              <button
                type="button"
                onClick={handleUpdateUserName}
                className="cyber-btn text-xs px-4 flex items-center gap-1.5"
              >
                <Save className="w-3.5 h-3.5" />
                Save
              </button>
            </div>
          </div>
        </GlassCard>

        {/* Wake Word & Voice Settings */}
        <GlassCard className="p-5 space-y-4 border-slate-800">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <Radio className="w-5 h-5 text-purple-400" />
              <h3 className="font-display font-bold text-sm text-white tracking-wider">
                WAKE WORD & VOICE PIPELINE
              </h3>
            </div>
            <button
              type="button"
              onClick={handleToggleVoicePipeline}
              className={`cyber-btn text-xs px-3 py-1.5 ${
                voicePipelineActive ? 'cyber-btn-danger' : 'cyber-btn-primary'
              }`}
            >
              <Mic className="w-3.5 h-3.5" />
              {voicePipelineActive ? 'Stop Pipeline' : 'Start Pipeline'}
            </button>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs font-tech">
              <span className="text-slate-400">PRIMARY WAKE WORD:</span>
              <span className="font-mono text-cyan-300 font-bold">
                "{identity?.wake_word || 'hey nexus'}"
              </span>
            </div>

            <div className="flex justify-between text-xs font-tech">
              <span className="text-slate-400">TTS SYNTHESIS PROVIDER:</span>
              <span className="font-mono text-purple-300">
                {voiceStatus?.pipeline?.tts_provider || 'Browser Neural / Edge TTS'}
              </span>
            </div>

            <div className="flex justify-between text-xs font-tech">
              <span className="text-slate-400">STT RECOGNITION PROVIDER:</span>
              <span className="font-mono text-emerald-300">
                {voiceStatus?.pipeline?.stt_provider || 'Google Web STT (Continuous)'}
              </span>
            </div>

            <div className="pt-2 border-t border-slate-800 space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-tech">
                  <span className="text-slate-300 font-semibold">UNIFIED ASSISTANT VOICE:</span>
                  <button
                    type="button"
                    onClick={handleTestVoice}
                    disabled={isTestingVoice}
                    className="cyber-btn text-[11px] px-2 py-0.5 flex items-center gap-1 border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10"
                    title="Test selected voice"
                  >
                    <Volume2 className={`w-3 h-3 ${isTestingVoice ? 'animate-bounce text-emerald-400' : ''}`} />
                    {isTestingVoice ? 'Testing Voice...' : 'Test Voice'}
                  </button>
                </div>
                <select
                  value={selectedVoiceName}
                  onChange={(e) => setSelectedVoiceName(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-cyan-300 focus:outline-none focus:border-cyan-400 font-sans"
                >
                  {availableVoices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-slate-500 font-sans">
                  The assistant uses this single consistent voice for all app commands, conversations, and questions.
                </p>
              </div>

              <div className="flex items-center justify-between text-xs font-tech pt-1">
                <span className="text-slate-300 font-semibold">AUTO VOICE RESPONSE:</span>
                <button
                  type="button"
                  onClick={() => setAutoVoiceResponse(!autoVoiceResponse)}
                  className={`px-2.5 py-1 rounded border font-mono text-[11px] transition-colors ${
                    autoVoiceResponse
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}
                >
                  {autoVoiceResponse ? 'ENABLED (ON)' : 'DISABLED (OFF)'}
                </button>
              </div>
            </div>
          </div>

          {/* Aliases List */}
          <div className="pt-3 border-t border-slate-800 space-y-3">
            <span className="font-tech text-xs text-slate-300 uppercase font-semibold">
              Wake Word Aliases ({identity?.aliases?.length || 0})
            </span>

            <div className="flex gap-2">
              <input
                type="text"
                value={newAlias}
                onChange={(e) => setNewAlias(e.target.value)}
                placeholder="New alias (e.g. computer, system)..."
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-400 font-mono"
              />
              <button
                type="button"
                disabled={!newAlias.trim() || isAddingAlias}
                onClick={handleAddAlias}
                className="cyber-btn text-xs px-3 py-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </div>

            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {(!identity?.aliases || identity.aliases.length === 0) ? (
                <div className="text-xs font-tech text-slate-500 py-2">
                  No secondary aliases configured.
                </div>
              ) : (
                identity.aliases.map((alias) => (
                  <div
                    key={alias}
                    className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800 text-xs font-mono"
                  >
                    <span className="text-cyan-300">"{alias}"</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveAlias(alias)}
                      className="text-slate-500 hover:text-rose-400 p-1"
                      title="Remove Alias"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};
