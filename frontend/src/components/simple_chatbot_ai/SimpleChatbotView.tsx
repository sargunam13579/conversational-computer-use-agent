import React, { useState, useEffect, useRef } from 'react';
import {
  User,
  Volume2,
  Plus,
  ArrowUp,
  Headphones,
  X,
  Edit3,
  Copy,
  Check,
  Image as ImageIcon,
  FileText,
  Paperclip,
} from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { useVoice } from '../../context/VoiceContext';
import { api } from '../../services/api';
import { ConvoComputerUseAgentView } from '../convo_computer_use_agent';

interface SimpleChatbotViewProps {
  onSendMessage?: (
    message: string,
    files?: File[]
  ) => void;

  externalPrompt?: string | null;
}

interface AttachedFile {
  name: string;
  size: number;

  type: 'image' | 'file';

  file: File;

  url?: string;
}

export const SimpleChatbotView: React.FC<SimpleChatbotViewProps> = ({
  onSendMessage,
  externalPrompt,
}) => {
  const {
    identity,
    messages,
    setMessages,
    isComputerUseActive,
    setIsComputerUseActive,
    setComputerUseMessages,
    setComputerUseConversationId,
  } = useNexus();

  const {
    isSpeaking,
    isProcessing,
    speakInstant,
    stopSpeaking,
    stopListening,
    setVoiceModeEnabled,
  } = useVoice();

  const [inputMessage, setInputMessage] = useState('');
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [speakingMsgIdx, setSpeakingMsgIdx] = useState<number | null>(null);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [editingMsgIdx, setEditingMsgIdx] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const addMenuRef = useRef<HTMLDivElement | null>(null);

  const userName = identity?.user_name || 'User';

  const handleToggleComputerUse = () => {
    if (!isComputerUseActive) {
      setComputerUseConversationId(null);
      setComputerUseMessages([]);
      setIsComputerUseActive(true);
      // Instant welcome greeting without self intro
      speakInstant(`Welcome ${userName}! Naan ready. Sollunga, enna pannalam?`);
    } else {
      setIsComputerUseActive(false);
      stopSpeaking();
      stopListening();
      setVoiceModeEnabled(false);
      api.stopComputerUse().catch(() => { });
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    }
  };

  // Handle external prompt selection from sidebar
  useEffect(() => {
    if (externalPrompt) {
      handleSend(externalPrompt);
    }
  }, [externalPrompt]);

  // Scroll to bottom on message updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

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

  const handleSend = (customText?: string) => {
    const text = (
      customText || inputMessage
    ).trim();

    if (!text && attachedFiles.length === 0) {
      return;
    }

    const actualFiles = attachedFiles.map(
      (item) => item.file
    );

    if (onSendMessage) {
      onSendMessage(
        text,
        actualFiles
      );
    }

    setInputMessage('');
    setAttachedFiles([]);
    setShowAddMenu(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
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
    setMessages((prev) =>
      prev.map((msg, i) => (i === idx ? { ...msg, content: trimmed } : msg))
    );
    setEditingMsgIdx(null);
  };

  const handleImageFileChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const files = e.target.files;

    if (!files || files.length === 0) {
      return;
    }

    const file = files[0];

    setAttachedFiles((prev) => [
      ...prev,
      {
        name: file.name,
        size: file.size,
        type: 'image',
        file,
        url: URL.createObjectURL(file),
      },
    ]);

    setShowAddMenu(false);

    if (imageInputRef.current) {
      imageInputRef.current.value = '';
    }
  };

  const handleDocFileChange = (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const files = e.target.files;

    if (!files || files.length === 0) {
      return;
    }

    const file = files[0];

    setAttachedFiles((prev) => [
      ...prev,
      {
        name: file.name,
        size: file.size,
        type: 'file',
        file,
      },
    ]);

    setShowAddMenu(false);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachedFile = (idx: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="flex flex-col h-full w-full relative overflow-hidden bg-[#070b14]">
      {/* Hidden File Inputs */}
      <input
        type="file"
        ref={imageInputRef}
        onChange={handleImageFileChange}
        accept="image/*"
        className="hidden"
      />
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleDocFileChange}
        accept="*/*"
        className="hidden"
      />

      {/* Top Header Bar: Clean NexUs Brand + Top-Right Headphone Agent Circle */}
      <div className="h-16 px-6 sm:px-10 border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-xl flex items-center justify-between shrink-0 z-30">
        <div className="flex items-center gap-3">
          <span className="font-display font-black text-xl sm:text-2xl tracking-wider text-white">
            Nex<span className="text-cyan-400">Us</span>
          </span>
        </div>

        {/* Top-Right Area: Back to Simple Chat Button + Headphone Circle */}
        <div className="flex items-center gap-3">
          {isComputerUseActive && (
            <button
              onClick={() => {
                setIsComputerUseActive(false);
                stopSpeaking();
                api.stopComputerUse().catch(() => { });
                if (typeof window !== 'undefined' && window.speechSynthesis) {
                  window.speechSynthesis.cancel();
                }
              }}
              className="flex items-center gap-1.5 text-xs text-slate-300 hover:text-white px-3.5 py-1.5 rounded-full bg-slate-900 border border-slate-700 hover:border-cyan-500/40 transition-all shadow-sm group"
              title="Return to Simple Chatbot"
            >
              <X className="w-3.5 h-3.5 text-cyan-400 group-hover:rotate-90 transition-transform" />
              <span>Back to Simple Chat</span>
            </button>
          )}

          <button
            onClick={handleToggleComputerUse}
            className={`relative group p-0.5 rounded-full transition-all duration-300 focus:outline-none ${isComputerUseActive
              ? 'ring-2 ring-cyan-400 shadow-[0_0_22px_rgba(0,240,255,0.6)] scale-105'
              : 'hover:ring-2 hover:ring-cyan-500/50 hover:shadow-[0_0_16px_rgba(0,240,255,0.3)]'
              }`}
            title="Click to toggle Conversational Computer-Use Agent Mode"
          >
            {/* Headphone Avatar Circle */}
            <div className="w-11 h-11 rounded-full bg-gradient-to-tr from-cyan-600 via-blue-600 to-indigo-600 flex items-center justify-center text-white border-2 border-slate-900 shadow-lg">
              <Headphones className="w-5 h-5 text-white group-hover:scale-110 transition-transform" />
            </div>

            {/* Glowing Active Status Badge */}
            <span
              className={`absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full border-2 border-slate-950 ${isComputerUseActive ? 'bg-cyan-400 animate-ping' : 'bg-emerald-400'
                }`}
            />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {isComputerUseActive ? (
        /* Conversational Computer-Use Agent View */
        <ConvoComputerUseAgentView />
      ) : (
        /* Simple Chatbot View with exact 15% left & 15% right space */
        <div className="flex-1 flex flex-col min-h-0 w-full overflow-hidden">
          {/* Messages Scroll Container (w-[70%] with 15% gutters on both sides) */}
          <div className="flex-1 overflow-y-auto px-2 pt-6 pb-4 custom-scrollbar w-full">
            <div className="w-[70%] mx-auto space-y-6">
              {/* Empty / Welcome State */}
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center min-h-[50vh] text-center animate-fadeIn select-none">
                  <h2 className="font-display font-black text-3xl sm:text-5xl text-white tracking-wide">
                    Hello {userName} 👋🏻
                  </h2>
                </div>
              )}

              {/* Message Bubbles */}
              {messages.map((msg, idx) => {
                const isUser = msg.role === 'user';
                const isEditing = editingMsgIdx === idx;

                return (
                  <div
                    key={idx}
                    className={`flex items-start gap-3.5 w-full animate-fadeIn group ${isUser ? 'justify-end' : 'justify-start'
                      }`}
                  >
                    {!isUser && (
                      <div className="w-8 h-8 rounded-full bg-cyan-600/20 border border-cyan-400/40 text-cyan-300 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                        N
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
                        <>
                          <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>

                          {/* User Message Footer: Edit Symbol Only + Text-Time */}
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

                          {/* Assistant Message Footer: Copy Symbol + Voice Symbol Only + Text-Time */}
                          {!isUser && msg.content && (
                            <div className="mt-3 pt-2.5 border-t border-slate-800/70 flex items-center justify-between text-xs text-slate-400">
                              <div className="flex items-center gap-2">
                                {/* Copy symbol */}
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

                                {/* Voice symbol only */}
                                <button
                                  onClick={() => handlePlayTTS(msg.content, idx)}
                                  className={`p-1 rounded-lg hover:bg-slate-800 transition-all ${isSpeaking && speakingMsgIdx === idx
                                    ? 'text-cyan-400 bg-slate-800'
                                    : 'text-slate-400 hover:text-cyan-300'
                                    }`}
                                  title={isSpeaking && speakingMsgIdx === idx ? 'Stop voice' : 'Listen voice'}
                                >
                                  <Volume2 className={`w-3.5 h-3.5 ${isSpeaking && speakingMsgIdx === idx ? 'animate-pulse' : ''}`} />
                                </button>
                              </div>

                              <span className="text-[10px] font-mono text-slate-500">
                                {msg.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                          )}
                        </>
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

              {isProcessing && (
                <div className="flex items-start gap-3.5 justify-start animate-fadeIn w-full">
                  <div className="w-8 h-8 rounded-full bg-cyan-600/20 border border-cyan-400/40 text-cyan-300 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                    N
                  </div>
                  <div className="p-5 rounded-2xl rounded-tl-sm bg-slate-900/90 border border-slate-800 text-slate-300 text-xs sm:text-sm font-mono flex items-center gap-2.5">
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                    <span>NexUs is thinking...</span>
                  </div>
                </div>
              )}

              <div className="h-4" />
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Dedicated Bottom Type-Bar Area (Non-overlapping flex sibling) */}
          <div className="shrink-0 w-full pb-6 pt-3 px-4 bg-gradient-to-t from-[#070b14] via-[#070b14]/95 to-transparent z-30">
            <div className="w-[70%] mx-auto relative">
              {/* Attachment Preview Chips */}
              {attachedFiles.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2 animate-fadeIn">
                  {attachedFiles.map((file, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-slate-900 border border-cyan-500/40 text-xs text-cyan-300 shadow-md backdrop-blur-xl"
                    >
                      {file.type === 'image' ? <ImageIcon className="w-3.5 h-3.5" /> : <Paperclip className="w-3.5 h-3.5" />}
                      <span className="truncate max-w-[150px]">{file.name}</span>
                      <button
                        onClick={() => removeAttachedFile(i)}
                        className="p-0.5 hover:text-rose-400 text-slate-400 ml-1"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Add (+) Menu Popup: Add Image, Add File */}
              {showAddMenu && (
                <div
                  ref={addMenuRef}
                  className="absolute bottom-16 left-0 p-1.5 rounded-2xl bg-slate-900/95 border border-slate-700 shadow-2xl shadow-black flex flex-col gap-1 w-44 animate-fadeIn backdrop-blur-xl z-50"
                >
                  <button
                    onClick={() => imageInputRef.current?.click()}
                    className="px-3 py-2 rounded-xl hover:bg-slate-800 text-slate-200 hover:text-cyan-300 text-xs font-medium flex items-center gap-2.5 transition-all text-left"
                  >
                    <ImageIcon className="w-4 h-4 text-cyan-400" />
                    <span>Add Image</span>
                  </button>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="px-3 py-2 rounded-xl hover:bg-slate-800 text-slate-200 hover:text-cyan-300 text-xs font-medium flex items-center gap-2.5 transition-all text-left"
                  >
                    <FileText className="w-4 h-4 text-amber-400" />
                    <span>Add File</span>
                  </button>
                </div>
              )}

              {/* Pill Input Bar */}
              <div className="flex items-center gap-2.5 px-4 py-3 rounded-full bg-slate-900/95 border border-slate-700/80 focus-within:border-cyan-400 focus-within:ring-2 focus-within:ring-cyan-500/20 backdrop-blur-2xl shadow-2xl shadow-black/80 transition-all">
                {/* Plus Button (+) */}
                <button
                  type="button"
                  onClick={() => setShowAddMenu(!showAddMenu)}
                  className="p-1.5 rounded-full hover:bg-slate-800 text-slate-400 hover:text-cyan-300 transition-all shrink-0 focus:outline-none"
                  title="Add Image / File"
                >
                  <Plus className={`w-5 h-5 transition-transform duration-200 ${showAddMenu ? 'rotate-45 text-cyan-400' : ''}`} />
                </button>

                {/* Text Input */}
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask NexUs..."
                  className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 text-sm sm:text-base focus:outline-none px-2 py-1"
                />

                {/* Send Button (↑) */}
                <button
                  type="button"
                  onClick={() => handleSend()}
                  disabled={!inputMessage.trim() && attachedFiles.length === 0}
                  className="w-9 h-9 rounded-full bg-cyan-400 hover:bg-cyan-300 disabled:opacity-30 disabled:hover:bg-cyan-400 text-slate-950 font-bold flex items-center justify-center transition-all shrink-0 shadow-md shadow-cyan-900/30 focus:outline-none"
                  title="Send Message"
                >
                  <ArrowUp className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
