import React, { useEffect, useRef } from 'react';
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

  // Central sendUserMessage for global voice / chat processing
  const sendUserMessage = async (messageText: string, source: 'voice' | 'chat' = 'voice') => {
    const query = messageText.trim();
    if (!query) return;

    // 1. Create unique requestId / turnId
    const turnId = getNextTurnId();
    console.log(`[USER TURN START] turnId=${turnId} source=${source} text="${query}"`);

    // 2. Cancel any active TTS speech immediately
    cancelCurrentSpeech(`user_${source}_input`);
    console.log(`[TTS CANCELLED] turnId=${turnId}`);
    setProcessing(true);

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
      const res = await api.sendMessage(query, activeConversationId || undefined);

      // 4. Validate that turnId is still active/latest
      if (turnId !== getCurrentTurnId()) {
        console.warn(`[STALE RESPONSE IGNORED] turnId=${turnId} activeTurnId=${getCurrentTurnId()}`);
        return;
      }

      console.log(`[AI RESPONSE RECEIVED] turnId=${turnId} response="${res.response}"`);

      if (res.conversation_id && res.conversation_id !== activeConversationId) {
        setActiveConversationId(res.conversation_id);
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

  // Register global transcript listener for continuous live speech detection
  useEffect(() => {
    const unregister = registerTranscriptHandler((transcriptText) => {
      if (transcriptText && transcriptText.trim()) {
        sendUserMessageRef.current(transcriptText, 'voice');
      }
    });
    return unregister;
  }, [registerTranscriptHandler]);

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
        return <SimpleChatbotView onSendMessage={(msg) => sendUserMessage(msg, 'chat')} />;
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

      {/* Backend connection warning banner if not connected */}
      {!isBackendConnected && !isLoading && (
        <div className="bg-rose-500/20 border-b border-rose-500/40 text-rose-300 text-xs px-6 py-2 flex items-center justify-between font-tech shrink-0">
          <span>
            ⚠️ BACKEND API DISCONNECTED (http://127.0.0.1:8000). Ensure the FastAPI server is running with <code className="font-mono bg-slate-900 px-1.5 py-0.5 rounded text-cyan-300">.\.venv\Scripts\python.exe -m nexus.main --mode api</code>.
          </span>
          <span className="animate-pulse font-mono font-bold">ATTEMPTING RECONNECT...</span>
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

export const App: React.FC = () => {
  return (
    <NexusProvider>
      <VoiceProvider>
        <MainContent />
      </VoiceProvider>
    </NexusProvider>
  );
};

export default App;
