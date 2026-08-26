import React, { useEffect, useState } from 'react';
import { Mic, MicOff, Volume2, VolumeX, X, Sparkles, Radio } from 'lucide-react';
import { useVoice, type VoiceStateType } from '../../context/VoiceContext';
import { useNexus } from '../../context/NexusContext';

interface ChatGPTVoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSendMessage?: (text: string) => void;
}

export const ChatGPTVoiceModal: React.FC<ChatGPTVoiceModalProps> = ({
  isOpen,
  onClose,
}) => {
  const {
    voiceState,
    isListening,
    isSpeaking,
    isProcessing,
    voiceModeEnabled,
    setVoiceModeEnabled,
    startContinuousListening,
    stopListening,
    cancelCurrentSpeech,
    transcript,
    interimTranscript,
    error,
  } = useVoice();

  const { identity } = useNexus();
  const assistantName = identity?.assistant_name || 'NEXUS';
  const userName = identity?.user_name || 'User';
  const [subtitle, setSubtitle] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setVoiceModeEnabled(true);
      startContinuousListening();
    }
  }, [isOpen, setVoiceModeEnabled, startContinuousListening]);

  useEffect(() => {
    if (interimTranscript) {
      setSubtitle(interimTranscript);
    } else if (transcript) {
      setSubtitle(transcript);
    }
  }, [interimTranscript, transcript]);

  if (!isOpen) return null;

  const getStateDetails = (state: VoiceStateType) => {
    switch (state) {
      case 'listening':
        return {
          title: 'Listening...',
          sub: 'Speak naturally anytime in English, Tamil, or Tanglish',
          orbColor: 'from-cyan-400 via-sky-500 to-blue-600',
          glow: 'shadow-[0_0_90px_rgba(14,165,233,0.6)]',
          ringColor: 'border-cyan-400/80',
          pulseSpeed: 'animate-pulse',
        };
      case 'processing':
        return {
          title: `${assistantName} is thinking...`,
          sub: 'Processing directive and reasoning...',
          orbColor: 'from-purple-500 via-indigo-500 to-pink-500',
          glow: 'shadow-[0_0_90px_rgba(168,85,247,0.6)]',
          ringColor: 'border-purple-400/80',
          pulseSpeed: 'animate-spin-slow',
        };
      case 'speaking':
        return {
          title: `${assistantName} is speaking...`,
          sub: 'Start speaking anytime to interrupt',
          orbColor: 'from-emerald-400 via-teal-500 to-cyan-500',
          glow: 'shadow-[0_0_100px_rgba(16,185,129,0.6)]',
          ringColor: 'border-emerald-400/80',
          pulseSpeed: 'animate-bounce-subtle',
        };
      case 'idle':
      default:
        return {
          title: 'Ready',
          sub: 'Tap the microphone or say something to start',
          orbColor: 'from-slate-600 via-slate-700 to-slate-800',
          glow: 'shadow-[0_0_40px_rgba(100,116,139,0.3)]',
          ringColor: 'border-slate-600',
          pulseSpeed: '',
        };
    }
  };

  const currentDetails = getStateDetails(voiceState);

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-between p-6 bg-slate-950/95 backdrop-blur-2xl transition-all duration-300 select-none">
      {/* Top Header */}
      <div className="w-full max-w-4xl flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-cyan-300">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-display font-bold text-white text-base tracking-wide">
                {assistantName}
              </span>
              <span className="text-[10px] font-tech uppercase px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                Voice Mode
              </span>
            </div>
            <p className="text-xs text-slate-400 font-sans">
              Connected with {userName || 'User'}
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-2.5 rounded-full bg-slate-900/80 border border-slate-700 hover:border-slate-500 text-slate-300 hover:text-white transition-all shadow-lg"
          title="Exit Voice Mode"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Center ChatGPT-Style Fluid Pulsating Orb */}
      <div className="relative flex flex-col items-center justify-center my-auto">
        {/* Outer Ripple Wave 1 */}
        <div
          className={`absolute w-72 h-72 rounded-full border border-dashed ${currentDetails.ringColor} opacity-40 transition-all duration-700 ${
            isSpeaking || isListening ? 'scale-125 animate-ping opacity-20' : 'scale-100'
          }`}
        />

        {/* Outer Ripple Wave 2 */}
        <div
          className={`absolute w-60 h-60 rounded-full border ${currentDetails.ringColor} opacity-50 transition-all duration-500 ${
            isSpeaking ? 'scale-110 animate-pulse' : 'scale-100'
          }`}
        />

        {/* Central Fluid Glowing Orb */}
        <div
          className={`relative w-48 h-48 rounded-full bg-gradient-to-tr ${currentDetails.orbColor} ${currentDetails.glow} flex items-center justify-center transition-all duration-500 ${
            isSpeaking
              ? 'scale-110'
              : isListening
              ? 'scale-105'
              : isProcessing
              ? 'scale-95'
              : 'scale-90 opacity-80'
          }`}
        >
          <div className="w-36 h-36 rounded-full bg-slate-950/80 backdrop-blur-md flex flex-col items-center justify-center border border-white/20 shadow-inner">
            {isSpeaking ? (
              <div className="flex items-center gap-1.5 h-8">
                {[40, 80, 60, 100, 75, 45, 90].map((h, i) => (
                  <div
                    key={i}
                    className="w-1 bg-emerald-400 rounded-full animate-sound-wave"
                    style={{
                      height: `${h}%`,
                      animationDelay: `${i * 0.12}s`,
                      animationDuration: '0.6s',
                    }}
                  />
                ))}
              </div>
            ) : isListening ? (
              <Radio className="w-10 h-10 text-cyan-300 animate-pulse" />
            ) : isProcessing ? (
              <div className="w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <Mic className="w-8 h-8 text-slate-400" />
            )}
          </div>
        </div>

        {/* Status Indicator */}
        <div className="text-center mt-10 space-y-1.5 max-w-md px-4">
          <h2 className="text-xl font-display font-semibold text-white tracking-wide">
            {currentDetails.title}
          </h2>
          <p className="text-xs font-sans text-slate-400 leading-relaxed">
            {currentDetails.sub}
          </p>
        </div>

        {/* Live Transcript / Subtitle Preview */}
        {subtitle && (
          <div className="mt-6 px-5 py-2.5 rounded-2xl bg-slate-900/80 border border-slate-800/80 text-sm text-cyan-200 font-sans text-center max-w-lg shadow-xl">
            "{subtitle}"
          </div>
        )}

        {/* Error notification if any */}
        {error && (
          <div className="mt-4 px-4 py-2 rounded-xl bg-rose-500/20 border border-rose-500/40 text-xs text-rose-300 font-sans text-center max-w-md">
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* Bottom Floating Control Bar */}
      <div className="w-full max-w-md flex items-center justify-center gap-6 mb-4">
        {/* Toggle Microphone Listening */}
        <button
          onClick={() => {
            if (voiceModeEnabled && isListening) {
              stopListening();
            } else {
              setVoiceModeEnabled(true);
              startContinuousListening();
            }
          }}
          className={`p-4 rounded-full border transition-all shadow-xl flex items-center justify-center ${
            voiceModeEnabled && isListening
              ? 'bg-cyan-500/20 border-cyan-400/80 text-cyan-300 shadow-[0_0_20px_rgba(14,165,233,0.4)]'
              : 'bg-slate-900/80 border-slate-700 text-slate-400 hover:border-slate-500 hover:text-white'
          }`}
          title={isListening ? 'Pause Microphone' : 'Activate Microphone'}
        >
          {isListening ? <Mic className="w-6 h-6" /> : <MicOff className="w-6 h-6" />}
        </button>

        {/* Stop / Interrupt Assistant Speech */}
        {isSpeaking && (
          <button
            onClick={() => cancelCurrentSpeech('user_stop_button')}
            className="px-6 py-3 rounded-full bg-rose-500/20 border border-rose-400/60 text-rose-300 font-sans text-sm font-medium hover:bg-rose-500/30 transition-all shadow-lg flex items-center gap-2 animate-pulse"
          >
            <VolumeX className="w-4 h-4" />
            <span>Interrupt Speech</span>
          </button>
        )}

        {/* Mute Voice Output */}
        <button
          onClick={() => {
            if (isSpeaking) {
              cancelCurrentSpeech('mute_toggle');
            }
          }}
          className="p-4 rounded-full bg-slate-900/80 border border-slate-700 hover:border-slate-500 text-slate-400 hover:text-white transition-all shadow-xl flex items-center justify-center"
          title="Audio Output State"
        >
          {isSpeaking ? <Volume2 className="w-6 h-6 text-emerald-400" /> : <Volume2 className="w-6 h-6" />}
        </button>
      </div>
    </div>
  );
};
