import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Monitor,
  Square,
  Layers,
  Send,
  Compass,
  Plus,
  ArrowUp,
  User,
  Volume2,
  Copy,
  Check,
  Edit3,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Mic,
  Sparkles,
} from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { useVoice } from '../../context/VoiceContext';
import { api } from '../../services/api';
import type { MessageItem } from '../../types';
import { ChatGPTVoiceModal } from '../common/ChatGPTVoiceModal';

interface StepItem {
  step: number;
  thought: string;
  action: string;
  coordinates: [number | null, number | null];
  success: boolean;
  elapsed_seconds: number;
}

export const ConvoComputerUseAgentView: React.FC = () => {
  const {
    computerUseMessages,
    setComputerUseMessages,
    computerUseConversationId,
    setComputerUseConversationId,
    addActivity,
    identity,
  } = useNexus();

  const {
    isListening,
    isSpeaking,
    interimTranscript,
    recognitionLang,
    setRecognitionLang,
    startListening,
    stopListening,
    speakInstant,
    speakAssistantResponse,
    getNextTurnId,
    stopSpeaking,
    setProcessing,
    setVoiceModeEnabled,
  } = useVoice();
  const userName = identity?.user_name || 'User';
  const wasVoiceTriggered = useRef<boolean>(true);
  const autoListen = true; // Always active internally for hands-free workflow
  const isMountedRef = useRef<boolean>(true);

  const [inputMessage, setInputMessage] = useState('');
  const [steerText, setSteerText] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);
  const [isTaskExecuting, setIsTaskExecuting] = useState(false);
  const isTaskExecutingRef = useRef<boolean>(false);
  isTaskExecutingRef.current = isTaskExecuting;

  const isBusy = isWaiting || isTaskExecuting;
  const isBusyRef = useRef<boolean>(false);
  isBusyRef.current = isBusy;

  const [agentStatus, setAgentStatus] = useState<string>('idle');
  const [liveSteps, setLiveSteps] = useState<StepItem[]>([]);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [speakingMsgIdx, setSpeakingMsgIdx] = useState<number | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [editingMsgIdx, setEditingMsgIdx] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const [expandedTraceIdx, setExpandedTraceIdx] = useState<number | null>(null);
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false);

  // Track component mount lifecycle
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Helper to start listening for user voice input (works across all subsequent turns)
  const triggerVoiceListen = useCallback(() => {
    if (!isMountedRef.current) return;
    wasVoiceTriggered.current = true;
    startListening((finalTranscript) => {
      if (!isMountedRef.current) return;
      if (finalTranscript && finalTranscript.trim()) {
        const spokenText = finalTranscript.trim();
        if (isTaskExecutingRef.current) {
          // If currently executing a real desktop task, spoken input acts as live voice steering
          handleVoiceSteer(spokenText);
        } else if (!isBusyRef.current) {
          // Start conversation or goal from spoken command
          handleSend(spokenText, true);
        }
      }
    }, recognitionLang || 'en-IN');
  }, [startListening, recognitionLang]);

  // Dynamic context-aware welcome greeting with once-per-session guard
  useEffect(() => {
    const welcomeSpoken = sessionStorage.getItem('ccua_session_welcome_spoken');
    if (!welcomeSpoken) {
      sessionStorage.setItem('ccua_session_welcome_spoken', 'true');
      api
        .getComputerUseWelcome(userName || 'Friend')
        .then((data) => {
          const welcomeText =
            data?.greeting ||
            `Good evening ${userName || 'Friend'}-nga! Naan ready. Innaiki enna interesting task seiyalam, sollunga! 😊✨`;

          const welcomeMsgId = 'welcome-' + Date.now();

          // 1. Initialize assistant message bubble with EMPTY text so it streams word-by-word in sync
          setComputerUseMessages((prev) => {
            if (prev.length === 0) {
              return [
                {
                  id: welcomeMsgId,
                  role: 'assistant',
                  content: '',
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  model_used: 'gemini-2.5-flash',
                },
              ];
            }
            return prev;
          });

          // 2. Speak using the EXACT SAME unified assistant voice engine (speakAssistantResponse) with simultaneous word-by-word streaming!
          const welcomeTurnId = getNextTurnId();
          speakAssistantResponse(
            welcomeText,
            welcomeTurnId,
            () => {
              // On End: Ensure full message is visible and auto-listen starts
              setComputerUseMessages((prev) => {
                const next = [...prev];
                if (next.length > 0 && next[0].id === welcomeMsgId) {
                  next[0] = { ...next[0], content: welcomeText };
                }
                return next;
              });
              if (isMountedRef.current && autoListen) {
                triggerVoiceListen();
              }
            },
            undefined,
            (revealedText) => {
              // Word-by-word simultaneous live karaoke sync with audio playback!
              setComputerUseMessages((prev) => {
                const next = [...prev];
                if (next.length > 0 && next[0].id === welcomeMsgId) {
                  next[0] = { ...next[0], content: revealedText };
                }
                return next;
              });
            }
          );
        })
        .catch(() => {
          const fallback = `Good evening ${userName || 'Friend'}-nga! Naan ready. Innaiki enna interesting task seiyalam, sollunga! 😊✨`;
          const welcomeTurnId = getNextTurnId();
          speakAssistantResponse(fallback, welcomeTurnId, () => {
            if (isMountedRef.current && autoListen) {
              triggerVoiceListen();
            }
          });
        });
    } else if (autoListen && !isListening && !isSpeaking && !isBusy) {
      // User navigated back from Simple Chat or other tab: Silent standby, do NOT repeat welcome!
      triggerVoiceListen();
    }
  }, []);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const addMenuRef = useRef<HTMLDivElement | null>(null);

  // Scroll to bottom on updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [computerUseMessages, isBusy, isTaskExecuting, liveSteps.length, interimTranscript]);

  // Simultaneous live speech streaming directly into user text-bar word-by-word
  useEffect(() => {
    if (interimTranscript && isListening && !isBusy) {
      const isStatusText =
        interimTranscript.includes('Listening') ||
        interimTranscript.includes('Recognizing') ||
        interimTranscript.includes('🎙️');
      if (!isStatusText && interimTranscript.trim()) {
        setInputMessage(interimTranscript);
      }
    }
  }, [interimTranscript, isListening, isBusy]);

  // Close add menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Cleanup on unmount (when user switches view or returns to simple chat)
  useEffect(() => {
    return () => {
      api.stopComputerUse().catch(() => { });
      stopSpeaking();
      stopListening();
      setVoiceModeEnabled(false);
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, [stopSpeaking, stopListening, setVoiceModeEnabled]);

  // Poll status when executing a task or waiting for response
  useEffect(() => {
    let interval: any = null;
    if (isBusy) {
      interval = setInterval(async () => {
        try {
          const res = await api.getComputerUseStatus();
          setAgentStatus(res.status);
          if (res.history) {
            setLiveSteps(res.history);
          }
          if (res.is_task) {
            setIsTaskExecuting(true);
            isTaskExecutingRef.current = true;
          }
          if (['completed', 'failed', 'stopped', 'idle'].includes(res.status) && !res.is_task) {
            setIsTaskExecuting(false);
            isTaskExecutingRef.current = false;
          }
        } catch (e) {
          console.debug('Status poll error', e);
        }
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isBusy]);

  const handleToggleMic = () => {
    if (isListening) {
      stopListening();
      wasVoiceTriggered.current = false;
    } else {
      triggerVoiceListen();
    }
  };

  const handleVoiceSteer = async (spokenSteer: string) => {
    if (!spokenSteer.trim()) return;
    try {
      await api.steerComputerUse(spokenSteer.trim(), true);
      addActivity({
        type: 'chat',
        title: 'Voice Steering Injected',
        detail: spokenSteer.trim(),
        status: 'info',
      });
      speakInstant(`Steering instruction received: ${spokenSteer}`);
    } catch (err: any) {
      console.error('Voice steer failed:', err);
    }
  };

  const computerUseConversationIdRef = useRef<string | null>(computerUseConversationId);
  useEffect(() => {
    computerUseConversationIdRef.current = computerUseConversationId;
  }, [computerUseConversationId]);

  const isNewChatIntent = (text: string) => {
    const lower = text.toLowerCase().trim();
    const keywords = [
      'new chat',
      'open new chat',
      'start new chat',
      'create new chat',
      'new chat open',
      'new chat start',
      'new conversation',
      'open a new chat',
      'start a new chat',
    ];
    return keywords.some((kw) => lower.includes(kw));
  };

  const handleSend = async (customGoal?: string, fromVoice = false) => {
    const goal = (customGoal || inputMessage).trim();
    if (!goal || isBusy) return;

    if (fromVoice) {
      wasVoiceTriggered.current = true;
    }

    let targetConvId = computerUseConversationIdRef.current;
    if (isNewChatIntent(goal)) {
      targetConvId = null;
      setComputerUseConversationId(null);
      computerUseConversationIdRef.current = null;
      setComputerUseMessages([]);
    }

    setInputMessage('');
    setShowAddMenu(false);

    const userMsg: MessageItem = {
      role: 'user',
      content: goal,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setComputerUseMessages((prev) => [...prev, userMsg]);
    setIsWaiting(true);
    setIsTaskExecuting(false);
    isTaskExecutingRef.current = false;
    setProcessing(true);
    setAgentStatus('thinking');
    setLiveSteps([]);

    addActivity({
      type: 'tool_exec',
      title: 'Conversational Computer-Use Started',
      detail: goal,
      status: 'info',
    });

    try {
      const res = await api.runComputerUseGoal(
        goal,
        20,
        true,
        targetConvId || undefined
      );

      if (res.conversation_id) {
        setComputerUseConversationId(res.conversation_id);
        computerUseConversationIdRef.current = res.conversation_id;
      }

      if (res.history) {
        setLiveSteps(res.history);
      }

      const stepsTaken = res.history ? res.history.length : 0;
      const isTask = res.intent === 'TASK' || res.is_task || stepsTaken > 0;
      const finalNarration =
        res.narration ||
        (isTask
          ? `Done-nga! Task successfully complete panniten (${stepsTaken} steps on Windows) 🎉`
          : 'Sollunga! Enna help pannattum? 😊✨');

      // Start assistant message with empty content for simultaneous word-by-word streaming
      const assistantMsg: MessageItem = {
        role: 'assistant',
        content: '',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        model_used: 'gemini-2.5-flash',
      };

      setComputerUseMessages((prev) => [...prev, assistantMsg]);

      // Release locks before starting speech
      setIsWaiting(false);
      setIsTaskExecuting(false);
      isTaskExecutingRef.current = false;
      setProcessing(false);
      setAgentStatus('idle');

      // Primary voice feedback: Simultaneous word-by-word speech & text reveal!
      const narrationTurnId = getNextTurnId();
      speakAssistantResponse(
        finalNarration,
        narrationTurnId,
        () => {
          // Speech ended: ensure complete message is displayed and resume listening
          setComputerUseMessages((prev) => {
            const next = [...prev];
            if (next.length > 0 && next[next.length - 1].role === 'assistant') {
              next[next.length - 1] = { ...next[next.length - 1], content: finalNarration };
            }
            return next;
          });
          if (autoListen && isMountedRef.current) {
            setTimeout(() => {
              triggerVoiceListen();
            }, 80);
          }
        },
        undefined,
        (revealedText) => {
          // Word-by-word text update simultaneous with speech audio!
          setComputerUseMessages((prev) => {
            const next = [...prev];
            if (next.length > 0 && next[next.length - 1].role === 'assistant') {
              next[next.length - 1] = { ...next[next.length - 1], content: revealedText };
            }
            return next;
          });
        }
      );

      addActivity({
        type: 'tool_exec',
        title: 'Computer-Use Goal Achieved',
        detail: finalNarration.slice(0, 100),
        status: 'success',
      });
    } catch (err: any) {
      console.error('Computer-use execution error:', err);
      const errMsg = err?.response?.data?.detail || err.message || 'Execution halted or timed out.';
      const assistantMsg: MessageItem = {
        role: 'assistant',
        content: `Error during computer-use execution: ${errMsg}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setComputerUseMessages((prev) => [...prev, assistantMsg]);
      speakInstant(`Error occurred: ${errMsg}`);
      addActivity({
        type: 'tool_exec',
        title: 'Computer-Use Error',
        detail: errMsg,
        status: 'error',
      });
    } finally {
      setIsWaiting(false);
      setIsTaskExecuting(false);
      isTaskExecutingRef.current = false;
      setProcessing(false);
      setAgentStatus('idle');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSteer = async () => {
    if (!steerText.trim()) return;
    try {
      await api.steerComputerUse(steerText.trim(), true);
      addActivity({
        type: 'chat',
        title: 'Live Steering Injected',
        detail: steerText.trim(),
        status: 'info',
      });
      setSteerText('');
    } catch (err: any) {
      console.error('Steer failed:', err);
    }
  };

  const handleStop = async () => {
    try {
      await api.stopComputerUse();
      setIsTaskExecuting(false);
      isTaskExecutingRef.current = false;
      setIsWaiting(false);
      setAgentStatus('stopped');
      addActivity({
        type: 'security',
        title: 'Computer-Use Emergency Stop',
        detail: 'Emergency stop signal sent.',
        status: 'warning',
      });
    } catch (err: any) {
      console.error(err);
    }
  };

  const handlePlayTTS = (text: string, idx: number) => {
    if (isSpeaking && speakingMsgIdx === idx) {
      stopSpeaking();
      setSpeakingMsgIdx(null);
    } else {
      setSpeakingMsgIdx(idx);
      speakInstant(text, () => setSpeakingMsgIdx(null));
    }
  };

  const handleCopyMessage = async (text: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    } catch {
      // Fallback
    }
  };

  const handleStartEdit = (idx: number, content: string) => {
    setEditingMsgIdx(idx);
    setEditingText(content);
  };

  const handleSaveEdit = (idx: number) => {
    const trimmed = editingText.trim();
    if (!trimmed) return;
    setComputerUseMessages((prev) =>
      prev.map((msg, i) => (i === idx ? { ...msg, content: trimmed } : msg))
    );
    setEditingMsgIdx(null);
  };

  const computerUsePresets = [
    {
      title: 'VS Code open பண்ணு',
      goal: 'VS Code open பண்ணு',
    },
    {
      title: 'Desktop Java folder open பண்ணு',
      goal: 'Desktop-la இருக்குற Java folder open பண்ணு',
    },
    {
      title: 'New file create panni palindrome code போடு',
      goal: 'New file create பண்ணி, check string palindrome code போடு',
    },
    {
      title: 'Code run பண்ணு',
      goal: 'Code run பண்ணு',
    },
    {
      title: 'Camera open panni photo edu',
      goal: 'Camera open panni photo edu',
    },
    {
      title: 'Delete "hello" and "hiii" chats',
      goal: '"hello" and "hiii" chats ah delete pannu',
    },
  ];

  return (
    <div className="flex-1 flex flex-col min-h-0 relative w-full h-full">
      {/* Hero Live Voice Waveform / Real-Time Speech Perception Banner */}
      <div className="px-6 pt-3 pb-1 shrink-0 w-full">
        <div className="w-[70%] mx-auto">
          {isListening ? (
            <div className="p-3.5 rounded-2xl bg-gradient-to-r from-cyan-950/80 via-slate-900/90 to-blue-950/80 border border-cyan-400/50 shadow-lg shadow-cyan-950/30 flex items-center justify-between gap-3 animate-fadeIn backdrop-blur-xl">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                {/* Pulsing Voice Equalizer Bars */}
                <div className="flex items-end gap-1 h-5 shrink-0 px-1">
                  <span className="w-1 bg-cyan-400 rounded-full animate-[bounce_0.8s_infinite_100ms] h-3" />
                  <span className="w-1 bg-cyan-300 rounded-full animate-[bounce_0.6s_infinite_200ms] h-5" />
                  <span className="w-1 bg-blue-400 rounded-full animate-[bounce_0.9s_infinite_150ms] h-4" />
                  <span className="w-1 bg-emerald-400 rounded-full animate-[bounce_0.7s_infinite_300ms] h-5" />
                  <span className="w-1 bg-cyan-400 rounded-full animate-[bounce_0.8s_infinite_250ms] h-3" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-bold text-cyan-300 tracking-wider uppercase">
                      🎙️ Voice Active — Listening to You...
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 font-medium truncate mt-0.5">
                    {interimTranscript ? (
                      <span className="text-cyan-300 font-semibold">“{interimTranscript}”</span>
                    ) : (
                      'Speak your task (e.g. "Open Camera and take a pic", "Delete hello chat")...'
                    )}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => setRecognitionLang(recognitionLang === 'ta-IN' ? 'en-IN' : 'ta-IN')}
                  className="px-2 py-1 rounded-xl bg-cyan-950/90 hover:bg-cyan-900 border border-cyan-400/50 text-[11px] font-mono text-cyan-300 flex items-center gap-1.5 transition-all shadow-sm"
                  title="Click to toggle between English/Tanglish and Tamil speech recognition"
                >
                  <RefreshCw className="w-3 h-3 text-cyan-400" />
                  <span>{recognitionLang === 'ta-IN' ? 'தமிழ் (ta-IN)' : 'English (en-IN)'}</span>
                </button>
                <button
                  onClick={stopListening}
                  className="px-2.5 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-300 border border-slate-700 shrink-0"
                >
                  Mute Mic
                </button>
              </div>
            </div>
          ) : isSpeaking ? (
            <div className="p-3 rounded-2xl bg-gradient-to-r from-purple-950/80 via-slate-900/90 to-indigo-950/80 border border-purple-500/50 shadow-lg shadow-purple-950/30 flex items-center justify-between gap-3 animate-fadeIn backdrop-blur-xl">
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <Volume2 className="w-4 h-4 text-purple-400 animate-pulse shrink-0" />
                <span className="text-xs font-mono text-purple-300 truncate">
                  🔊 Seyal AI Speaking live response...
                </span>
              </div>
              <button
                onClick={stopSpeaking}
                className="px-2.5 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-300 border border-slate-700 shrink-0"
              >
                Stop Speech
              </button>
            </div>
          ) : isTaskExecuting ? (
            <div className="p-3 rounded-2xl bg-gradient-to-r from-amber-950/70 via-slate-900/90 to-slate-950/80 border border-amber-500/40 shadow-lg flex items-center justify-between gap-3 animate-fadeIn backdrop-blur-xl">
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <Compass className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
                <span className="text-xs font-mono text-amber-300 truncate">
                  ⚡ Autonomous Computer Task Running — Speak anytime to voice-steer or tap stop
                </span>
              </div>
              <button
                onClick={triggerVoiceListen}
                className="px-2.5 py-1 rounded-xl bg-amber-900/40 hover:bg-amber-900/60 border border-amber-500/50 text-[11px] font-mono text-amber-200 shrink-0"
              >
                🎙️ Speak Steer
              </button>
            </div>
          ) : isWaiting ? (
            <div className="p-2.5 rounded-2xl bg-slate-900/80 border border-cyan-500/30 flex items-center justify-between gap-3 text-xs text-cyan-300 animate-fadeIn">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <Sparkles className="w-3.5 h-3.5 text-cyan-400 animate-pulse shrink-0" />
                <span className="text-[11px] font-mono text-cyan-200 truncate">
                  Seyal AI is thinking & preparing response...
                </span>
              </div>
            </div>
          ) : (
            <div className="p-2.5 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between gap-3 text-xs text-slate-400">
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <Mic className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span className="text-[11px] font-mono text-slate-300 truncate">
                  Primary Voice Input Ready ({recognitionLang === 'ta-IN' ? 'தமிழ்' : 'English / Tanglish'}) — Tap mic below or start speaking
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => setRecognitionLang(recognitionLang === 'ta-IN' ? 'en-IN' : 'ta-IN')}
                  className="px-2 py-0.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[10px] font-mono text-cyan-300"
                  title="Toggle speech recognition language"
                >
                  {recognitionLang === 'ta-IN' ? 'தமிழ்' : 'English'}
                </button>
                <button
                  onClick={triggerVoiceListen}
                  className="px-2.5 py-0.5 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-500/40 text-[11px] font-mono text-cyan-300"
                >
                  Start Voice
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Messages Scroll Container (w-[70%] with 15% gutters on both sides) */}
      <div className="flex-1 overflow-y-auto px-2 pt-6 pb-4 custom-scrollbar w-full">
        <div className="w-[70%] mx-auto space-y-6">
          {/* Message Bubbles */}
          {computerUseMessages.map((msg, idx) => {
            const isUser = msg.role === 'user';
            const isEditing = editingMsgIdx === idx;
            const isTraceExpanded = expandedTraceIdx === idx;

            return (
              <div
                key={idx}
                className={`flex items-start gap-3.5 w-full animate-fadeIn group ${isUser ? 'justify-end' : 'justify-start'
                  }`}
              >
                {!isUser && (
                  <div className="w-8 h-8 rounded-full bg-cyan-600/20 border border-cyan-400/40 text-cyan-300 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                    <Monitor className="w-4 h-4 text-cyan-400" />
                  </div>
                )}

                <div
                  className={`relative max-w-[85%] p-5 rounded-2xl text-sm sm:text-base leading-relaxed ${isUser
                    ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white rounded-tr-sm shadow-md shadow-cyan-950/20'
                    : 'bg-slate-900/90 border border-slate-800/90 text-slate-200 rounded-tl-sm shadow-sm'
                    }`}
                >
                  {/* Message Content or Edit Input */}
                  {isEditing ? (
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={editingText}
                        onChange={(e) => setEditingText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveEdit(idx);
                          if (e.key === 'Escape') setEditingMsgIdx(null);
                        }}
                        className="w-full bg-slate-950/80 border border-cyan-300 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none"
                        autoFocus
                      />
                      <div className="flex items-center justify-end gap-2 text-xs">
                        <button
                          onClick={() => handleSaveEdit(idx)}
                          className="px-2.5 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingMsgIdx(null)}
                          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <p className="whitespace-pre-wrap leading-relaxed">
                        {msg.content ? (
                          <>
                            {msg.content}
                            {!isUser && idx === computerUseMessages.length - 1 && isSpeaking && (
                              <span className="inline-block w-1.5 h-4 ml-1 bg-cyan-400 animate-pulse align-middle" />
                            )}
                          </>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-cyan-400 py-1">
                            <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                            <span className="text-xs font-mono text-slate-400">Seyal AI speaking...</span>
                          </span>
                        )}
                      </p>

                      {/* Vision-Action Step Summary Card if Assistant */}
                      {!isUser && liveSteps.length > 0 && idx === computerUseMessages.length - 1 && (
                        <div className="mt-4 pt-3 border-t border-slate-800/80">
                          <button
                            onClick={() => setExpandedTraceIdx(isTraceExpanded ? null : idx)}
                            className="flex items-center justify-between w-full text-xs font-mono text-cyan-400 hover:text-cyan-300 py-1"
                          >
                            <span className="flex items-center gap-1.5">
                              <Layers className="w-3.5 h-3.5" />
                              Vision-Action Execution Trace ({liveSteps.length} Steps)
                            </span>
                            {isTraceExpanded ? (
                              <ChevronUp className="w-3.5 h-3.5" />
                            ) : (
                              <ChevronDown className="w-3.5 h-3.5" />
                            )}
                          </button>

                          {isTraceExpanded && (
                            <div className="mt-2.5 space-y-2 max-h-60 overflow-y-auto custom-scrollbar pr-1">
                              {liveSteps.map((step, sIdx) => (
                                <div
                                  key={sIdx}
                                  className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs space-y-1"
                                >
                                  <div className="flex items-center justify-between">
                                    <span className="font-mono text-cyan-400 font-bold">
                                      STEP #{step.step}
                                    </span>
                                    <span className="font-mono text-[10px] text-slate-400">
                                      {step.elapsed_seconds}s • {step.action}
                                    </span>
                                  </div>
                                  <p className="text-slate-300 text-[11px] italic">
                                    "{step.thought}"
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* User Message Footer */}
                  {isUser && !isEditing && (
                    <div className="mt-3 pt-2.5 border-t border-cyan-400/30 flex items-center justify-between text-xs text-cyan-100/80">
                      <button
                        onClick={() => handleStartEdit(idx, msg.content)}
                        className="p-1 rounded-lg hover:bg-cyan-700/50 hover:text-white transition-all text-cyan-200"
                        title="Edit message"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <span className="text-[10px] font-mono opacity-80">
                        {msg.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  )}

                  {/* Assistant Message Footer */}
                  {!isUser && msg.content && (
                    <div className="mt-3 pt-2.5 border-t border-slate-800/70 flex items-center justify-between text-xs text-slate-400">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleCopyMessage(msg.content, idx)}
                          className="p-1 rounded-lg hover:bg-slate-800 hover:text-cyan-300 transition-all text-slate-400"
                          title={copiedIdx === idx ? 'Copied!' : 'Copy message'}
                        >
                          {copiedIdx === idx ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>

                        <button
                          onClick={() => handlePlayTTS(msg.content, idx)}
                          className={`p-1 rounded-lg hover:bg-slate-800 transition-all ${isSpeaking && speakingMsgIdx === idx
                            ? 'text-cyan-400 bg-slate-800'
                            : 'text-slate-400 hover:text-cyan-300'
                            }`}
                          title={isSpeaking && speakingMsgIdx === idx ? 'Stop voice' : 'Listen voice'}
                        >
                          <Volume2
                            className={`w-3.5 h-3.5 ${isSpeaking && speakingMsgIdx === idx ? 'animate-pulse' : ''
                              }`}
                          />
                        </button>
                      </div>

                      <span className="text-[10px] font-mono text-slate-500">
                        {msg.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  )}
                </div>

                {isUser && (
                  <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 text-slate-200 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })}

          {/* Active Computer-Use Execution Progress Bubble (ONLY for real desktop OS tasks!) */}
          {isTaskExecuting && (
            <div className="flex items-start gap-3.5 justify-start animate-fadeIn w-full">
              <div className="w-8 h-8 rounded-full bg-cyan-600/20 border border-cyan-400/40 text-cyan-300 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                <Monitor className="w-4 h-4 text-cyan-400 animate-spin" />
              </div>
              <div className="p-4 rounded-2xl rounded-tl-sm bg-slate-900/95 border border-cyan-500/40 text-slate-200 text-xs sm:text-sm font-mono space-y-2 max-w-[85%] shadow-lg shadow-cyan-950/30">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2 text-cyan-300 font-bold">
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                    <span>Agent Status: {agentStatus.toUpperCase()}</span>
                  </div>
                  <span className="text-[10px] text-slate-400">
                    {liveSteps.length} step(s) executed
                  </span>
                </div>

                {liveSteps.length > 0 && (
                  <p className="text-[11px] text-slate-300 italic bg-slate-950/60 p-2 rounded-lg border border-slate-800">
                    Latest Step #{liveSteps[liveSteps.length - 1].step}: {liveSteps[liveSteps.length - 1].thought}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Conversational Thinking Indicator (ONLY when waiting for chat response, NOT a task) */}
          {isWaiting && !isTaskExecuting && (
            <div className="flex items-start gap-3.5 justify-start animate-fadeIn w-full">
              <div className="w-8 h-8 rounded-full bg-cyan-600/20 border border-cyan-400/40 text-cyan-300 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                <Sparkles className="w-4 h-4 text-cyan-400 animate-pulse" />
              </div>
              <div className="p-3.5 rounded-2xl rounded-tl-sm bg-slate-900/90 border border-cyan-500/30 text-slate-300 text-xs font-mono flex items-center gap-2 shadow-lg shadow-cyan-950/20">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                <span className="text-cyan-300 font-semibold">Seyal is thinking...</span>
              </div>
            </div>
          )}

          <div className="h-4" />
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Dedicated Bottom User Text-Bar Area (Non-overlapping flex sibling) */}
      <div className="shrink-0 w-full pb-6 pt-3 px-4 bg-gradient-to-t from-[#070b14] via-[#070b14]/95 to-transparent z-30">
        <div className="w-[70%] mx-auto relative space-y-2">
          {/* Live Steering & Stop Bar ONLY when an actual computer-use task is executing! */}
          {isTaskExecuting && (
            <div className="p-2.5 rounded-2xl bg-slate-900/95 border border-amber-500/40 backdrop-blur-2xl shadow-xl shadow-black/80 flex items-center gap-2 animate-fadeIn">
              <div className="flex items-center gap-1.5 text-xs font-mono text-amber-400 font-semibold px-2 shrink-0">
                <Compass className="w-4 h-4 animate-spin" />
                <span className="hidden sm:inline">LIVE STEER:</span>
              </div>
              <input
                type="text"
                value={steerText}
                onChange={(e) => setSteerText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSteer()}
                placeholder="Inject mid-task instruction (e.g. 'Click second button instead', 'Wait')..."
                className="flex-1 bg-transparent text-xs text-amber-200 placeholder-amber-500/60 focus:outline-none px-2"
              />
              <button
                onClick={handleSteer}
                disabled={!steerText.trim()}
                className="px-3 py-1 bg-amber-600/30 hover:bg-amber-600/50 border border-amber-500/50 disabled:opacity-30 text-amber-200 text-xs font-semibold rounded-xl flex items-center gap-1"
              >
                <Send className="w-3 h-3" />
                <span>Steer</span>
              </button>
              <button
                onClick={handleStop}
                className="px-3 py-1 bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/50 text-rose-300 text-xs font-semibold rounded-xl flex items-center gap-1"
                title="Emergency Stop"
              >
                <Square className="w-3 h-3 fill-rose-400" />
                <span className="hidden sm:inline">Stop</span>
              </button>
            </div>
          )}

          {/* Plus (+) Menu Popup: Quick Presets */}
          {showAddMenu && (
            <div
              ref={addMenuRef}
              className="absolute bottom-16 left-0 p-2 rounded-2xl bg-slate-900/95 border border-slate-700 shadow-2xl shadow-black flex flex-col gap-1 w-64 animate-fadeIn backdrop-blur-xl z-50"
            >
              <span className="text-[10px] font-mono text-slate-400 uppercase px-2.5 py-1">Preset Recipes</span>
              {computerUsePresets.map((preset, i) => (
                <button
                  key={i}
                  onClick={() => {
                    handleSend(preset.goal);
                    setShowAddMenu(false);
                  }}
                  className="px-3 py-1.5 rounded-xl hover:bg-slate-800 text-slate-300 hover:text-white text-xs truncate transition-all text-left"
                  title={preset.goal}
                >
                  • {preset.title}
                </button>
              ))}
            </div>
          )}

          {/* Pill Input Bar */}
          <div className="flex items-center gap-2.5 px-4 py-3 rounded-full bg-slate-900/95 border border-slate-700/80 focus-within:border-cyan-400 focus-within:ring-2 focus-within:ring-cyan-500/20 backdrop-blur-2xl shadow-2xl shadow-black/80 transition-all">
            {/* Plus Button (+) */}
            <button
              type="button"
              onClick={() => setShowAddMenu(!showAddMenu)}
              className="p-1.5 rounded-full hover:bg-slate-800 text-slate-400 hover:text-cyan-300 transition-all shrink-0 focus:outline-none"
              title="Preset Recipes"
            >
              <Plus
                className={`w-5 h-5 transition-transform duration-200 ${showAddMenu ? 'rotate-45 text-cyan-400' : ''
                  }`}
              />
            </button>

            {/* Text Input (with real-time simultaneous voice streaming) */}
            <div className="flex-1 flex items-center relative">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isBusy}
                placeholder="Type or speak computer instruction..."
                className="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm sm:text-base focus:outline-none px-2 py-1 disabled:opacity-50"
              />
              {isListening && interimTranscript && (
                <span className="absolute right-2 flex items-center gap-1.5 text-[11px] font-mono text-cyan-400 pointer-events-none animate-pulse bg-slate-950/80 px-2 py-0.5 rounded-md border border-cyan-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                  Live Voice
                </span>
              )}
            </div>

            {/* Language Switcher Pill (Tamil/Tanglish vs English) */}
            <button
              type="button"
              onClick={() => setRecognitionLang(recognitionLang === 'ta-IN' ? 'en-IN' : 'ta-IN')}
              disabled={isBusy}
              className="px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-cyan-400/50 text-xs font-mono text-cyan-300 flex items-center gap-1.5 transition-all shrink-0 focus:outline-none"
              title="Click to toggle voice language between Tamil/Tanglish and English"
            >
              <span>{recognitionLang === 'ta-IN' ? '🇮🇳 தமிழ் / Tanglish' : '🌐 English'}</span>
            </button>

            {/* Primary Live Voice Microphone Button */}
            <button
              type="button"
              onClick={handleToggleMic}
              disabled={isBusy}
              className={`relative px-3.5 py-2 rounded-full flex items-center gap-2 transition-all shrink-0 focus:outline-none ${isListening
                ? 'bg-gradient-to-r from-rose-600 to-pink-600 text-white shadow-[0_0_20px_rgba(244,63,94,0.6)] scale-105 ring-2 ring-rose-300 animate-pulse'
                : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold shadow-[0_0_16px_rgba(0,240,255,0.4)] hover:scale-105'
                }`}
              title={isListening ? 'Listening live... Tap to mute' : 'Tap to speak voice command'}
            >
              <Mic className={`w-4 h-4 ${isListening ? 'text-white animate-bounce' : 'text-slate-950'}`} />
              <span className="text-xs font-mono font-semibold hidden sm:inline">
                {isListening ? 'Listening...' : 'Voice Input'}
              </span>
            </button>

            {/* Fullscreen ChatGPT Voice Mode Trigger Button */}
            <button
              type="button"
              onClick={() => setIsVoiceModalOpen(true)}
              disabled={isBusy}
              className="p-2 rounded-full bg-gradient-to-tr from-cyan-500/20 to-purple-500/20 hover:from-cyan-500/35 hover:to-purple-500/35 border border-cyan-400/40 hover:border-cyan-300 text-cyan-300 hover:text-white transition-all duration-300 shadow-sm shadow-cyan-950/30 hover:scale-105 active:scale-95 shrink-0 focus:outline-none disabled:opacity-40"
              title="Launch Fullscreen Voice Conversation Mode (ChatGPT Style)"
            >
              <Sparkles className="w-4 h-4 text-cyan-300 animate-pulse" />
            </button>

            {/* Send Button (↑) for Typed Input */}
            <button
              type="button"
              onClick={() => handleSend()}
              disabled={!inputMessage.trim() || isBusy}
              className="w-9 h-9 rounded-full bg-slate-800 hover:bg-slate-700 disabled:opacity-20 text-slate-300 hover:text-white font-bold flex items-center justify-center transition-all shrink-0 border border-slate-700 focus:outline-none"
              title="Send Typed Message"
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>
        </div>
      </div>

      {/* ChatGPT-Style Fullscreen Live Voice Modal (Conversational Computer-Use Agent ONLY) */}
      <ChatGPTVoiceModal
        isOpen={isVoiceModalOpen}
        onClose={() => setIsVoiceModalOpen(false)}
        onSendMessage={(spokenTask) => {
          if (isTaskExecutingRef.current) {
            handleVoiceSteer(spokenTask);
          } else {
            handleSend(spokenTask, true);
          }
        }}
      />
    </div>
  );
};
