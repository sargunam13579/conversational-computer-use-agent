import React, { useEffect, useRef, useState } from 'react';
import { NexusProvider, useNexus } from './context/NexusContext';
import { VoiceProvider, useVoice } from './context/VoiceContext';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { ConfirmationModal } from './components/common/ConfirmationModal';
import { DashboardView } from './components/views/DashboardView';
import { SimpleChatbotView } from './components/simple_chatbot_ai';
import { ConvoComputerUseAgentView } from './components/convo_computer_use_agent';
import { SystemControlView } from './components/views/SystemControlView';
import { ApplicationsView } from './components/views/ApplicationsView';
import { FilesView } from './components/views/FilesView';
import { DevicesView } from './components/views/DevicesView';
import { AutomationsView } from './components/views/AutomationsView';
import { ActivityView } from './components/views/ActivityView';
import { SettingsView } from './components/views/SettingsView';
import { api } from './services/api';
import type { MessageItem, ToolCallInfo } from './types';

const MainContent: React.FC = () => {
  const {
    activeView,
    isBackendConnected,
    isLoading,
    setMessages,
    addActivity,
    activeConversationId,
    setActiveConversationId,
    isComputerUseActive,
  } = useNexus();
  const {
    cancelCurrentSpeech,
    getNextTurnId,
    getCurrentTurnId,
    registerTranscriptHandler,
    setProcessing,
  } = useVoice();

  const welcomeExecutedRef = useRef<boolean>(false);

  const [showDisconnectBanner, setShowDisconnectBanner] = useState<boolean>(false);

  useEffect(() => {
    let timer: any = null;
    if (!isBackendConnected && !isLoading) {
      // Delay showing warning banner by 6s to allow initial Python startup
      timer = setTimeout(() => {
        setShowDisconnectBanner(true);
      }, 6000);
    } else {
      setShowDisconnectBanner(false);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [isBackendConnected, isLoading]);

  const activeConversationIdRef = useRef<string | null>(activeConversationId);
  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);


  // Central sendUserMessage for global voice / chat processing
  const sendUserMessage = async (messageText: string, source: 'voice' | 'chat' = 'voice', files: File[] = []) => {    // User voice-input feature is restricted strictly to Conversational Computer-Use Agent
    if (source === 'voice' && !isComputerUseActive) {
      console.log('[VOICE INPUT SKIPPED] Voice input is disabled for Simple Chatbot.');
      return;
    }

    const query = messageText.trim();
    if (!query) return;

    // 1. Create unique requestId / turnId
    const turnId = getNextTurnId();
    console.log(`[USER TURN START] turnId=${turnId} source=${source} text="${query}"`);

    // 2. Cancel any active TTS speech immediately
    cancelCurrentSpeech(`user_${source}_input`);
    console.log(`[TTS CANCELLED] turnId=${turnId}`);
    setProcessing(true);

    const targetConvId = activeConversationIdRef.current;


    const userMsg: MessageItem = {
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    };

    // Render user text in chat
    setMessages((prev) => [...prev, userMsg]);

    addActivity({
      type: 'chat',
      title: source === 'voice' ? 'Voice Directive' : 'Chat Directive',
      detail: query.slice(0, 90),
      status: 'info',
    });

    try {
      // 3. Send single request to AI
      console.log(`[FRONTEND API REQUEST] turnId=${turnId}`);
      const res = await api.sendMessage(
        query,
        targetConvId || undefined,
        files
      );
      // 4. Validate that turnId is still active/latest
      if (turnId !== getCurrentTurnId()) {
        console.warn(`[STALE RESPONSE IGNORED] turnId=${turnId} activeTurnId=${getCurrentTurnId()}`);
        return;
      }

      console.log(`[AI RESPONSE RECEIVED] turnId=${turnId} response="${res.response}"`);

      if (res.conversation_id) {
        setActiveConversationId(res.conversation_id);
        activeConversationIdRef.current = res.conversation_id;
      }

      // 5. Display response text smoothly without auto TTS audio playback
      const finalResponseText = res.response;
      const words = finalResponseText.split(/\s+/).filter(Boolean);

      const assistantMsg: MessageItem = {
        role: 'assistant',
        content: '',
        model_used: res.model_used || 'gemini-2.5-flash',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        tool_calls: res.tool_calls || [],
      };

      setProcessing(false);

      if (words.length <= 1) {
        setMessages((prev) => [...prev, { ...assistantMsg, content: finalResponseText }]);
      } else {
        setMessages((prev) => [...prev, { ...assistantMsg, content: '' }]);
        let currentWordIdx = 0;
        const streamInterval = setInterval(() => {
          currentWordIdx++;
          const visibleText = words.slice(0, currentWordIdx).join(' ');
          setMessages((prev) => {
            if (prev.length === 0) return prev;
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (updated[lastIdx].role === 'assistant') {
              updated[lastIdx] = { ...updated[lastIdx], content: visibleText };
            }
            return updated;
          });

          if (currentWordIdx >= words.length) {
            clearInterval(streamInterval);
          }
        }, 35);
      }

      if (res.tool_calls && res.tool_calls.length > 0) {
        addActivity({
          type: 'tool_exec',
          title: `Executed ${res.tool_calls.map((t: ToolCallInfo) => t.name).join(', ')}`,
          detail: finalResponseText.slice(0, 100),
          status: 'success',
        });
      }
    } catch (err: any) {
      if (turnId !== getCurrentTurnId()) {
        console.warn(`[STALE RESPONSE IGNORED ON ERROR] id=${turnId}`);
        return;
      }

      console.error('[AI] Request failed:', err);
      const rawDetail = String(err?.response?.data?.detail || err?.message || '');
      const finalErrorText = 'Please check your internet connection.';

      const errorMsg: MessageItem = {
        role: 'assistant',
        content: finalErrorText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
      setProcessing(false);

      addActivity({
        type: 'chat',
        title: 'Network Notice',
        detail: rawDetail || 'Connection timeout / offline',
        status: 'error',
      });
    } finally {
      if (turnId === getCurrentTurnId()) {
        setProcessing(false);
      }
    }
  };

  const sendUserMessageRef = useRef(sendUserMessage);
  useEffect(() => {
    sendUserMessageRef.current = sendUserMessage;
  });

  // User voice input is strictly for Conversational Computer-Use Agent. Unregister/ignore for simple chatbot.
  useEffect(() => {
    if (!isComputerUseActive) return;
    const unregister = registerTranscriptHandler((transcriptText) => {
      if (isComputerUseActive && transcriptText && transcriptText.trim()) {
        sendUserMessageRef.current(transcriptText, 'voice');
      }
    });
    return unregister;
  }, [registerTranscriptHandler, isComputerUseActive]);

  // Session startup: Ready and idle until user provides first input
  useEffect(() => {
    if (welcomeExecutedRef.current) return;
    if (!isBackendConnected && isLoading) return;
    welcomeExecutedRef.current = true;
  }, [isBackendConnected, isLoading]);

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return <DashboardView />;
      case 'assistant':
        return (
          <SimpleChatbotView
            onSendMessage={(msg, files) =>
              sendUserMessage(msg, 'chat', files)
            }
          />
        );
      case 'computer_use':
        return <ConvoComputerUseAgentView />;
      case 'system':
        return <SystemControlView />;
      case 'applications':
        return <ApplicationsView />;
      case 'files':
        return <FilesView />;
      case 'devices':
        return <DevicesView />;
      case 'automations':
        return <AutomationsView />;
      case 'activity':
        return <ActivityView />;
      case 'settings':
        return <SettingsView />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#060911] text-slate-100 select-none">
      {/* Top Header HUD - Hidden in Simple Chatbot mode, visible in Conversational Computer-Use Agent and other OS views */}
      {!(activeView === 'assistant' && !isComputerUseActive) && <Header />}

      {/* Backend connection warning banner if not connected after grace period */}
      {showDisconnectBanner && (
        <div className="bg-rose-500/20 border-b border-rose-500/40 text-rose-300 text-xs px-6 py-2 flex items-center justify-between font-tech shrink-0">
          <span>
            ⚠️ Connecting to AI Engine (http://127.0.0.1:8000)...
          </span>
          <span className="animate-pulse font-mono font-bold">RECONNECTING...</span>
        </div>
      )}

      {/* Main OS Body: Sidebar + Active View Workspace */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <Sidebar onSelectPrompt={(prompt) => sendUserMessage(prompt, 'chat')} />
        <main className={`flex-1 min-h-0 overflow-y-auto ${activeView === 'assistant' ? 'p-0' : 'p-4 md:p-6 lg:p-7'}`}>
          {renderView()}
        </main>
      </div>

      <ConfirmationModal />
    </div>
  );
};

import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './components/auth/LoginPage';
import { ProfileSetupPage } from './components/auth/ProfileSetupPage';

const AuthenticatedApp: React.FC = () => {
  const { session, loading } = useAuth();
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileSetupRequired, setProfileSetupRequired] = useState(false);
  const checkedUserIdRef = useRef<string | null>(null);

  const userId = session?.user?.id;

  useEffect(() => {
    if (!userId) {
      checkedUserIdRef.current = null;
      setProfileLoading(false);
      return;
    }

    // If profile has already been verified for this logged-in user, do not trigger loading screen or re-sync
    if (checkedUserIdRef.current === userId) {
      return;
    }

    const checkAndSyncProfile = async () => {
      try {
        setProfileLoading(true);
        const res = await api.getProfile();

        if (res.setup_required) {
          // If setup is required in PostgreSQL, check if we have user metadata from signup
          const metadata = session?.user?.user_metadata;
          if (metadata && metadata.name && metadata.age && metadata.gender) {
            try {
              // Silently sync metadata to backend PostgreSQL
              await api.setupProfile({
                name: metadata.name,
                age: Number(metadata.age),
                gender: metadata.gender,
              });
              setProfileSetupRequired(false);
            } catch (syncErr) {
              console.error('Failed to sync signup metadata to backend:', syncErr);
              setProfileSetupRequired(true);
            }
          } else {
            setProfileSetupRequired(true);
          }
        } else {
          setProfileSetupRequired(false);
        }
        checkedUserIdRef.current = userId;
      } catch (err) {
        console.error('Failed to fetch profile:', err);
        // Avoid getting permanently stuck on loading screen on error
        checkedUserIdRef.current = userId;
      } finally {
        setProfileLoading(false);
      }
    };

    checkAndSyncProfile();
  }, [userId, session]);

  if (loading || (session && profileLoading)) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#060911] text-slate-100 font-sans">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium text-slate-400">
          {loading ? 'Connecting to Nexus Auth...' : 'Loading User Profile...'}
        </p>
      </div>
    );
  }

  if (!session) {
    return <LoginPage />;
  }

  if (profileSetupRequired) {
    return (
      <ProfileSetupPage
        onComplete={() => setProfileSetupRequired(false)}
      />
    );
  }

  return (
    <NexusProvider>
      <VoiceProvider>
        <MainContent />
      </VoiceProvider>
    </NexusProvider>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
};

export default App;
