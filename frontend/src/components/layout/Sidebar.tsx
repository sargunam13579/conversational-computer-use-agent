import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  MessageSquarePlus,
  MessageSquare,
  MoreVertical,
  Edit2,
  Pin,
  Trash2,
  Check,
  X,
  LogOut,
  Sparkles,
  Sliders,
  Settings,
  HelpCircle,
  ChevronRight,
} from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import type { ConversationSummary } from '../../types';

interface SidebarProps {
  onSelectPrompt?: (promptText: string) => void;
}

const PINNED_STORAGE_KEY = 'nexus_pinned_conversation_ids';

export const Sidebar: React.FC<SidebarProps> = () => {
  const {
    isComputerUseActive,
    activeConversationId,
    setActiveConversationId,
    identity,
    resetChatContext,
    messages,
    setMessages,
    setActiveView,
  } = useNexus();

  const { signOut, user } = useAuth();

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);

  // Close profile dropdown when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) {
        setProfileMenuOpen(false);
      }
    };
    if (profileMenuOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [profileMenuOpen]);

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(PINNED_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [showSearchInput, setShowSearchInput] = useState(false);
  const [menuOpenConvId, setMenuOpenConvId] = useState<string | null>(null);
  const [renamingConvId, setRenamingConvId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');

  const menuRef = useRef<HTMLDivElement | null>(null);

  const loadConversations = async () => {
    try {
      const res = await api.listConversations(1, 50);
      setConversations(res.conversations || []);
    } catch (err) {
      console.debug('Failed to load conversations in sidebar:', err);
    }
  };

  useEffect(() => {
    loadConversations();
  }, [activeConversationId, messages.length, isComputerUseActive]);

  // Save pinned IDs to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify(pinnedIds));
    } catch {
      // Best effort
    }
  }, [pinnedIds]);

  // Close 3-dot menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenConvId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectConversation = async (convId: string) => {
    if (renamingConvId === convId) return;
    setActiveConversationId(convId);
    setActiveView('assistant');
    try {
      const detail = await api.getConversation(convId);
      if (detail && detail.messages) {
        setMessages(
          detail.messages.map((m) => ({
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: m.timestamp
              ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : undefined,
          }))
        );
      }
    } catch (err) {
      console.error('Failed to load conversation details:', err);
    }
  };

  const handleTogglePin = (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setPinnedIds((prev) =>
      prev.includes(convId) ? prev.filter((id) => id !== convId) : [convId, ...prev]
    );
    setMenuOpenConvId(null);
  };

  const handleStartRename = (conv: ConversationSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingConvId(conv.id);
    const cleanName = (conv.summary || 'Chat Session').replace(/^\[Computer-Use\]\s*/i, '');
    setRenameText(cleanName);
    setMenuOpenConvId(null);
  };

  const handleSaveRename = async (convId: string) => {
    const trimmed = renameText.trim();
    if (!trimmed) {
      setRenamingConvId(null);
      return;
    }
    const finalSummary = isComputerUseActive ? `[Computer-Use] ${trimmed}` : trimmed;
    try {
      await api.updateConversation(convId, finalSummary);
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, summary: finalSummary } : c))
      );
    } catch (err) {
      console.error('Failed to rename conversation:', err);
    } finally {
      setRenamingConvId(null);
    }
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      setPinnedIds((prev) => prev.filter((id) => id !== convId));
      if (activeConversationId === convId) {
        resetChatContext();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    } finally {
      setMenuOpenConvId(null);
    }
  };

  // Filter conversations strictly by active mode:
  // Simple Chatbot mode -> only show non-[Computer-Use] chats
  // Conversational Computer-Use Agent mode -> only show [Computer-Use] chats
  const modeConversations = conversations.filter((c) => {
    const isCU = (c.summary || '').startsWith('[Computer-Use]');
    return isComputerUseActive ? isCU : !isCU;
  });

  // Sort conversations: Pinned first, then by date
  const sortedConversations = [...modeConversations].sort((a, b) => {
    const aPinned = pinnedIds.includes(a.id);
    const bPinned = pinnedIds.includes(b.id);
    if (aPinned && !bPinned) return -1;
    if (!aPinned && bPinned) return 1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  const filteredConversations = sortedConversations.filter((c) => {
    const displayTitle = (c.summary || 'Chat session').replace(/^\[Computer-Use\]\s*/i, '');
    return displayTitle.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const userName = identity?.user_name || '';

  return (
    <aside className="w-64 glass-panel rounded-none border-t-0 border-l-0 border-b-0 border-r border-cyan-500/20 flex flex-col justify-between py-4 px-2 select-none bg-slate-950/85 backdrop-blur-2xl shrink-0 h-full">
      {/* Top Header: NexUs Brand Logo + Search Icon */}
      <div className="space-y-3 px-1.5 shrink-0">
        <div className="flex items-center justify-between px-2 pt-1 pb-2 border-b border-slate-800/80">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_10px_#00f0ff] animate-pulse" />
            <span className="font-display font-black text-xl tracking-wider text-white">
              Nex<span className="text-cyan-400">Us</span>
            </span>
          </div>

          <button
            onClick={() => setShowSearchInput(!showSearchInput)}
            className="p-1.5 rounded-lg bg-slate-900/60 hover:bg-cyan-500/20 text-slate-400 hover:text-cyan-300 border border-slate-800 transition-all"
            title="Search Chats"
          >
            <Search className="w-4 h-4" />
          </button>
        </div>

        {/* Search Input Filter */}
        {showSearchInput && (
          <div className="px-1 animate-fadeIn">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={isComputerUseActive ? "Search agent tasks..." : "Search chats..."}
              className="w-full px-3 py-1.5 bg-slate-900 border border-cyan-500/40 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
              autoFocus
            />
          </div>
        )}

        {isComputerUseActive && (
          <div className="px-2 flex items-center justify-between pt-1">
            <span className="text-[11px] font-mono text-cyan-400 uppercase tracking-wider font-semibold">
              AGENT HISTORY
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              {filteredConversations.length}
            </span>
          </div>
        )}
      </div>

      {/* Middle Scrollable Chat History */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-1 py-2 my-2 space-y-3 relative">
        {filteredConversations.length === 0 ? (
          <div className="text-center py-14 px-3 mx-1 border border-dashed border-slate-800/80 rounded-2xl">
            <MessageSquare className="w-6 h-6 text-slate-700 mx-auto mb-2" />
            <p className="text-slate-500 text-xs font-medium">
              {isComputerUseActive ? 'No agent tasks yet.' : 'No previous chats yet.'}
            </p>
            <p className="text-slate-600 text-[10px] mt-1">
              {isComputerUseActive ? 'Start a computer-use task to see history.' : 'Start a conversation to see your history here.'}
            </p>
          </div>
        ) : (
          filteredConversations.map((conv) => {
            const isActive = activeConversationId === conv.id;
            const isPinned = pinnedIds.includes(conv.id);
            const isRenaming = renamingConvId === conv.id;
            const isMenuOpen = menuOpenConvId === conv.id;
            const displayTitle = (conv.summary || 'Chat Session').replace(/^\[Computer-Use\]\s*/i, '');

            return (
              <div
                key={conv.id}
                className={`relative w-full rounded-2xl group transition-all duration-200 border my-2 mx-0.5 ${isActive
                  ? 'bg-cyan-500/15 text-cyan-200 border-cyan-500/50 shadow-md shadow-cyan-950/25 ring-1 ring-cyan-500/30'
                  : 'bg-slate-900/50 hover:bg-slate-900/90 border-slate-800/90 hover:border-slate-700 text-slate-300 hover:text-white shadow-sm'
                  }`}
              >
                {isRenaming ? (
                  /* Inline Rename Input */
                  <div className="flex items-center gap-1.5 p-2.5 w-full">
                    <input
                      type="text"
                      value={renameText}
                      onChange={(e) => setRenameText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveRename(conv.id);
                        if (e.key === 'Escape') setRenamingConvId(null);
                      }}
                      autoFocus
                      className="flex-1 bg-slate-950 border border-cyan-400 rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none"
                    />
                    <button
                      onClick={() => handleSaveRename(conv.id)}
                      className="p-1.5 rounded-md bg-emerald-950/60 border border-emerald-500/40 text-emerald-400 hover:text-emerald-300"
                      title="Save"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setRenamingConvId(null)}
                      className="p-1.5 rounded-md bg-rose-950/60 border border-rose-500/40 text-rose-400 hover:text-rose-300"
                      title="Cancel"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  /* Normal Chat Card with enhanced padding and margins */
                  <div
                    onClick={() => handleSelectConversation(conv.id)}
                    className="flex items-center justify-between p-3 px-3.5 cursor-pointer w-full"
                  >
                    <div className="flex items-center gap-2.5 truncate flex-1 pr-1.5">
                      {isPinned ? (
                        <Pin className="w-3.5 h-3.5 text-cyan-400 shrink-0 fill-cyan-400/40" />
                      ) : (
                        <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-cyan-400' : 'text-slate-500 group-hover:text-cyan-400'}`} />
                      )}
                      <span className="truncate text-xs font-medium tracking-wide">
                        {displayTitle}
                      </span>
                    </div>

                    {/* 3-Dots Setting Button with Generous Hit-Target */}
                    <div className="relative shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuOpenConvId(isMenuOpen ? null : conv.id);
                        }}
                        className={`p-1.5 rounded-lg transition-all ${isMenuOpen
                          ? 'bg-slate-800 text-cyan-300 border border-cyan-500/30'
                          : 'text-slate-400 hover:text-white hover:bg-slate-800/80 group-hover:opacity-100 opacity-60'
                          }`}
                        title="Chat options"
                      >
                        <MoreVertical className="w-3.5 h-3.5" />
                      </button>

                      {/* Dropdown Menu: Rename, Pin, Delete */}
                      {isMenuOpen && (
                        <div
                          ref={menuRef}
                          className="absolute right-0 top-8 w-36 rounded-2xl bg-slate-900/95 border border-slate-700 shadow-2xl z-50 p-1 text-xs animate-fadeIn backdrop-blur-2xl"
                        >
                          <button
                            onClick={(e) => handleStartRename(conv, e)}
                            className="w-full px-3 py-2 rounded-xl flex items-center gap-2 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                          >
                            <Edit2 className="w-3.5 h-3.5 text-cyan-400" />
                            <span>Rename</span>
                          </button>
                          <button
                            onClick={(e) => handleTogglePin(conv.id, e)}
                            className="w-full px-3 py-2 rounded-xl flex items-center gap-2 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                          >
                            <Pin className="w-3.5 h-3.5 text-amber-400" />
                            <span>{isPinned ? 'Unpin' : 'Pin Chat'}</span>
                          </button>
                          <div className="border-t border-slate-800 my-1" />
                          <button
                            onClick={(e) => handleDeleteConversation(conv.id, e)}
                            className="w-full px-3 py-2 rounded-xl flex items-center gap-2 text-rose-400 hover:text-rose-300 hover:bg-rose-950/50 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Bottom Footer: [New Chat] Button + User Avatar Profile */}
      <div className="pt-3 border-t border-slate-800/80 space-y-3 shrink-0 px-1">
        <button
          onClick={async () => {
            await resetChatContext();
            loadConversations();
            setActiveView('assistant');
          }}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-full bg-cyan-600/20 hover:bg-cyan-600/35 border border-cyan-500/40 hover:border-cyan-400 text-cyan-200 font-semibold text-xs tracking-wider transition-all shadow-sm shadow-cyan-950/30"
        >
          <MessageSquarePlus className="w-4 h-4 text-cyan-400" />
          <span>{isComputerUseActive ? 'New Agent Task' : 'New Chat'}</span>
        </button>

        {/* User Profile Pop-up Menu Trigger & Menu Box */}
        <div ref={profileMenuRef} className="relative">
          {/* Pop-up Menu */}
          {profileMenuOpen && (
            <div className="absolute bottom-full left-0 mb-2 w-60 bg-slate-950/95 border border-slate-800/80 rounded-xl p-3 shadow-2xl z-50 animate-fade-in space-y-2 backdrop-blur-xl">
              {/* Header profile info */}
              <div className="flex items-center gap-2.5 p-2 border-b border-slate-800/80 pb-3">
                <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center text-white font-bold text-xs border border-cyan-300/40 shadow-sm shrink-0">
                  {userName ? userName.charAt(0).toUpperCase() : 'U'}
                </div>
                <div className="flex flex-col truncate flex-grow">
                  <span className="text-xs font-semibold text-slate-200 truncate">{userName || 'User'}</span>
                  <span className="text-[10px] text-slate-500 truncate">{user?.email || 'dev@nexus.local'}</span>
                  <span className="text-[10px] font-semibold text-cyan-400 mt-0.5">Free</span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-500 shrink-0" />
              </div>

              {/* Menu Actions */}
              <div className="space-y-1 py-1">
                <button
                  onClick={() => setProfileMenuOpen(false)}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-900 rounded-lg transition-all text-left"
                >
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <span>Upgrade plan</span>
                </button>

                <button
                  onClick={() => setProfileMenuOpen(false)}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-900 rounded-lg transition-all text-left"
                >
                  <Sliders className="w-4 h-4 text-indigo-400" />
                  <span>Personalization</span>
                </button>



                <button
                  onClick={() => {
                    setProfileMenuOpen(false);
                    setActiveView('settings');
                  }}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-900 rounded-lg transition-all text-left"
                >
                  <Settings className="w-4 h-4 text-slate-400" />
                  <span>Settings</span>
                </button>

                <button
                  onClick={() => setProfileMenuOpen(false)}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-slate-300 hover:text-white hover:bg-slate-900 rounded-lg transition-all text-left"
                >
                  <HelpCircle className="w-4 h-4 text-slate-400" />
                  <span>Help</span>
                </button>
              </div>

              {/* Logout button */}
              <div className="border-t border-slate-800/80 pt-2">
                <button
                  onClick={() => {
                    setProfileMenuOpen(false);
                    signOut();
                  }}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2 text-xs text-rose-400 hover:bg-rose-950/20 hover:text-rose-300 rounded-lg transition-all text-left"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Log out</span>
                </button>
              </div>
            </div>
          )}

          {/* User Profile Avatar Footer Circle */}
          <div
            onClick={() => setProfileMenuOpen(!profileMenuOpen)}
            className="flex items-center justify-between px-2.5 py-2 rounded-xl bg-slate-900/60 hover:bg-slate-900/90 border border-slate-800/70 hover:border-slate-700 transition-all cursor-pointer select-none"
          >
            <div className="flex items-center gap-2.5 truncate">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center text-white font-bold text-xs border border-cyan-300/40 shadow-sm shrink-0">
                {userName ? userName.charAt(0).toUpperCase() : 'U'}
              </div>
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-slate-200 truncate">{userName || 'User'}</span>
                <span className="text-[10px] font-mono text-cyan-400">Online • Active</span>
              </div>
            </div>
            <div className="flex items-center text-slate-500 hover:text-white transition-all mr-0.5">
              <ChevronRight className="w-4 h-4 transform rotate-90" />
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};
