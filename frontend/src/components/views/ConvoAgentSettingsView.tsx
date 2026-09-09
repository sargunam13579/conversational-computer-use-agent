import React, { useState, useEffect } from 'react';
import {
  Search,
  Settings,
  Bell,
  Clock,
  Puzzle,
  CreditCard,
  MessageSquare,
  TrendingUp,
  Database,
  HardDrive,
  Shield,
  Key,
  Users,
  Globe,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Plus,
  Trash2,
  Save,
  Radio,
  Mic,
} from 'lucide-react';
import { useNexus } from '../../context/NexusContext';
import { useVoice } from '../../context/VoiceContext';
import { api } from '../../services/api';
import type { VoiceStatusResponse } from '../../types';

interface VoicePreset {
  id: string;
  name: string;
  description: string;
  gender: 'Female' | 'Male';
  locale: string;
  gradientClass: string;
}

const VOICE_PRESETS: VoicePreset[] = [
  {
    id: 'en-US-AvaNeural',
    name: 'Breeze',
    description: 'Animated and earnest',
    gender: 'Female',
    locale: 'Auto-detect',
    gradientClass: 'from-[#5468ff] via-[#8fa5ff] to-[#ffffff]',
  },
  {
    id: 'ta-IN-PallaviNeural',
    name: 'Pallavi',
    description: 'Natural and sweet — Tamil Female',
    gender: 'Female',
    locale: 'Tamil (India)',
    gradientClass: 'from-[#10b981] via-[#06b6d4] to-[#c7d2fe]',
  },
  {
    id: 'en-IN-NeerjaNeural',
    name: 'Neerja',
    description: 'Warm and friendly — Indian English',
    gender: 'Female',
    locale: 'Indian English',
    gradientClass: 'from-[#fb923c] via-[#f43f5e] to-[#fed7aa]',
  },
  {
    id: 'en-US-AndrewNeural',
    name: 'Andrew',
    description: 'Polite and warm — Conversational Male',
    gender: 'Male',
    locale: 'English (US)',
    gradientClass: 'from-[#3b82f6] via-[#6366f1] to-[#cbd5e1]',
  },
  {
    id: 'en-US-BrianNeural',
    name: 'Brian',
    description: 'Crisp and expressive — Studio Male',
    gender: 'Male',
    locale: 'English (US)',
    gradientClass: 'from-[#14b8a6] via-[#0284c7] to-[#e2e8f0]',
  },
  {
    id: 'en-US-EmmaNeural',
    name: 'Emma',
    description: 'Soft and thoughtful — Expressive Female',
    gender: 'Female',
    locale: 'English (US)',
    gradientClass: 'from-[#f472b6] via-[#c084fc] to-[#fdf2f8]',
  },
  {
    id: 'en-IN-PrabhatNeural',
    name: 'Prabhat',
    description: 'Articulate and clear — Indian English Male',
    gender: 'Male',
    locale: 'Indian English',
    gradientClass: 'from-[#f97316] via-[#eab308] to-[#fef08a]',
  },
  {
    id: 'ta-IN-ValluvarNeural',
    name: 'Valluvar',
    description: 'Traditional and deep — Tamil Male',
    gender: 'Male',
    locale: 'Tamil (India)',
    gradientClass: 'from-[#64748b] via-[#3b82f6] to-[#e2e8f0]',
  },
];

export const ConvoAgentSettingsView: React.FC = () => {
  const { identity, requestNameChange, refreshState, addActivity } = useNexus();
  const {
    autoVoiceResponse,
    setAutoVoiceResponse,
    selectedVoiceName,
    setSelectedVoiceName,
  } = useVoice();

  // Active tab state — default to 'voice' to match requested screenshot
  const [activeTab, setActiveTab] = useState<string>('voice');
  const [searchQuery, setSearchQuery] = useState('');

  // Assistant name state
  const [targetName, setTargetName] = useState('');
  const [nameChangeStatus, setNameChangeStatus] = useState<string | null>(null);
  const [isChangingName, setIsChangingName] = useState(false);

  // User profile details state
  const [userNameInput, setUserNameInput] = useState(identity?.user_name || '');
  const [userAgeInput, setUserAgeInput] = useState('');
  const [userGenderInput, setUserGenderInput] = useState('male');
  const [fetchingProfile, setFetchingProfile] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{ text: string; isError: boolean } | null>(null);

  // Alias state
  const [newAlias, setNewAlias] = useState('');
  const [isAddingAlias, setIsAddingAlias] = useState(false);

  // Voice settings state
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatusResponse | null>(null);
  const [voicePipelineActive, setVoicePipelineActive] = useState(false);

  // Dropdown states for Voice tab
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showLangDropdown, setShowLangDropdown] = useState(false);
  const [selectedModelName, setSelectedModelName] = useState('Live');
  const [selectedLanguageName, setSelectedLanguageName] = useState('Auto-detect');

  // Fetch profile on mount
  useEffect(() => {
    const fetchProfile = async () => {
      setFetchingProfile(true);
      try {
        const res = await api.getProfile();
        if (!res.setup_required && res.profile) {
          setUserNameInput(res.profile.name || '');
          setUserAgeInput(res.profile.age?.toString() || '');
          setUserGenderInput(res.profile.gender || 'male');
        } else {
          setUserNameInput(identity?.user_name || '');
        }
      } catch (err) {
        console.warn('Failed to load profile details in settings:', err);
        setUserNameInput(identity?.user_name || '');
      } finally {
        setFetchingProfile(false);
      }
    };
    fetchProfile();
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

  // Voice index calculation
  const currentVoiceIndex = Math.max(
    0,
    VOICE_PRESETS.findIndex((v) => v.id === selectedVoiceName)
  );
  const currentVoice = VOICE_PRESETS[currentVoiceIndex] || VOICE_PRESETS[0];

  const handlePrevVoice = () => {
    const nextIdx = (currentVoiceIndex - 1 + VOICE_PRESETS.length) % VOICE_PRESETS.length;
    setSelectedVoiceName(VOICE_PRESETS[nextIdx].id);
  };

  const handleNextVoice = () => {
    const nextIdx = (currentVoiceIndex + 1) % VOICE_PRESETS.length;
    setSelectedVoiceName(VOICE_PRESETS[nextIdx].id);
  };

  const handleSelectDot = (idx: number) => {
    setSelectedVoiceName(VOICE_PRESETS[idx].id);
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

  const handleUpdateUserProfile = async () => {
    setProfileMessage(null);
    const parsedAge = parseInt(userAgeInput, 10);
    if (!userNameInput.trim()) {
      setProfileMessage({ text: 'Please enter your name.', isError: true });
      return;
    }
    if (isNaN(parsedAge) || parsedAge < 1 || parsedAge > 120) {
      setProfileMessage({ text: 'Please enter a valid age between 1 and 120.', isError: true });
      return;
    }

    setSavingProfile(true);
    try {
      const res = await api.setupProfile({
        name: userNameInput.trim(),
        age: parsedAge,
        gender: userGenderInput,
      });

      if (res.success) {
        setProfileMessage({ text: 'Profile updated successfully!', isError: false });
        addActivity({
          type: 'identity',
          title: 'Operator Profile Updated',
          detail: `User profile updated (Name: ${userNameInput.trim()}, Age: ${parsedAge}, Gender: ${userGenderInput})`,
          status: 'success',
        });
        await refreshState();
      } else {
        setProfileMessage({ text: res.message || 'Failed to update profile.', isError: true });
      }
    } catch (err: any) {
      setProfileMessage({ text: err?.response?.data?.detail || err.message || 'An error occurred.', isError: true });
    } finally {
      setSavingProfile(false);
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

  // List of sidebar items matching screenshot
  const sidebarItems = [
    { id: 'general', label: 'General', icon: Settings },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'personalization', label: 'Personalization', icon: Clock },
    { id: 'plugins', label: 'Plugins', icon: Puzzle },
    { id: 'voice', label: 'Voice', isCustomWaveform: true },
    { id: 'billing', label: 'Billing', icon: CreditCard },
    { id: 'usage', label: 'Usage', icon: MessageSquare },
    { id: 'analytics', label: 'Analytics', icon: TrendingUp },
    { id: 'data_controls', label: 'Data controls', icon: Database },
    { id: 'storage', label: 'Storage', icon: HardDrive },
    { id: 'safety', label: 'Safety', icon: Shield },
    { id: 'security_login', label: 'Security and login', icon: Key },
    { id: 'parental_controls', label: 'Parental controls', icon: Users },
    { id: 'trusted_contact', label: 'Trusted contact', icon: Globe },
  ];

  const filteredSidebarItems = sidebarItems.filter((item) =>
    item.label.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full w-full flex items-center justify-center p-3 sm:p-6 bg-black/60 backdrop-blur-md select-none animate-fadeIn">
      {/* ChatGPT-style Settings Modal Frame */}
      <div className="w-full max-w-[820px] h-[600px] max-h-[92vh] bg-[#1c1c1e] border border-zinc-800/90 rounded-2xl shadow-2xl shadow-black flex overflow-hidden text-zinc-100 relative">
        
        {/* Left Category Sidebar */}
        <div className="w-60 shrink-0 bg-[#161618] border-r border-zinc-800/80 flex flex-col p-3.5">
          {/* Search settings input */}
          <div className="relative mb-3">
            <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search settings"
              className="w-full bg-zinc-800/60 border border-zinc-700/40 rounded-xl pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-500 transition-all font-sans"
            />
          </div>

          {/* Categories List */}
          <div className="flex-1 overflow-y-auto pr-1 space-y-0.5 custom-scrollbar">
            {filteredSidebarItems.map((item) => {
              const isActive = activeTab === item.id;
              const IconComponent = item.icon;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium text-left transition-all ${
                    isActive
                      ? 'bg-zinc-800 text-white font-semibold shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
                  }`}
                >
                  {/* Waveform icon for Voice matching screenshot */}
                  {item.isCustomWaveform ? (
                    <svg
                      className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-zinc-400'}`}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    >
                      <path d="M12 3v18M16 7v10M8 7v10M20 11v2M4 11v2" />
                    </svg>
                  ) : IconComponent ? (
                    <IconComponent className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-zinc-400'}`} />
                  ) : null}
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Content Area */}
        <div className="flex-1 flex flex-col bg-[#1c1c1e] overflow-hidden">
          
          {/* TAB: VOICE (Exact Match to User's Screenshot) */}
          {activeTab === 'voice' && (
            <div className="flex-1 flex flex-col h-full animate-fadeIn">
              {/* Header */}
              <div className="px-8 py-5 border-b border-zinc-800/80 shrink-0">
                <h2 className="text-base font-semibold text-zinc-100">Voice</h2>
              </div>

              {/* Central Voice Carousel */}
              <div className="flex-1 flex flex-col items-center justify-center px-8 py-6">
                {/* Glowing Voice Orb */}
                <div className="relative flex items-center justify-center mb-6">
                  {/* Outer diffuse glow */}
                  <div
                    className={`absolute w-36 h-36 rounded-full bg-gradient-to-tr ${currentVoice.gradientClass} opacity-40 blur-2xl transition-all duration-700`}
                  />
                  {/* Inner Voice Sphere */}
                  <div
                    className={`relative w-32 h-32 rounded-full bg-gradient-to-tr ${currentVoice.gradientClass} shadow-xl shadow-indigo-950/40 flex items-center justify-center transition-all duration-700`}
                  >
                    {/* Soft atmospheric radial gradient overlay */}
                    <div className="w-full h-full rounded-full bg-radial from-transparent via-white/10 to-black/20" />
                  </div>
                </div>

                {/* Voice Navigation: Left Arrow, Name & Description, Right Arrow */}
                <div className="flex items-center justify-center gap-6 w-full max-w-sm mb-4">
                  <button
                    type="button"
                    onClick={handlePrevVoice}
                    className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800/60 rounded-full transition-all shrink-0"
                    title="Previous voice"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>

                  <div className="text-center min-w-[200px]">
                    <h3 className="text-xl font-bold text-white tracking-wide">
                      {currentVoice.name}
                    </h3>
                    <p className="text-xs text-zinc-400 mt-1 font-normal">
                      {currentVoice.description}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={handleNextVoice}
                    className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800/60 rounded-full transition-all shrink-0"
                    title="Next voice"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>

                {/* Pagination Dots */}
                <div className="flex items-center justify-center gap-1.5 mb-10">
                  {VOICE_PRESETS.map((v, idx) => (
                    <button
                      key={v.id}
                      type="button"
                      onClick={() => handleSelectDot(idx)}
                      className={`h-1.5 rounded-full transition-all ${
                        idx === currentVoiceIndex
                          ? 'w-2 bg-white'
                          : 'w-1.5 bg-zinc-600 hover:bg-zinc-400'
                      }`}
                      title={v.name}
                    />
                  ))}
                </div>

                {/* Bottom Settings Rows with dividers matching screenshot */}
                <div className="w-full max-w-md space-y-4 pt-4 border-t border-zinc-800/80">
                  {/* Row 1: Model */}
                  <div className="flex items-center justify-between text-xs py-1 relative">
                    <span className="text-zinc-200 font-medium">Model</span>
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setShowModelDropdown(!showModelDropdown)}
                        className="text-zinc-400 hover:text-zinc-200 font-medium flex items-center gap-1.5 transition-colors focus:outline-none"
                      >
                        <span>{selectedModelName}</span>
                        <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
                      </button>

                      {showModelDropdown && (
                        <div className="absolute right-0 bottom-7 w-48 bg-zinc-900 border border-zinc-700/80 rounded-xl shadow-xl p-1 z-30 space-y-0.5">
                          {['Live', 'Edge Neural Engine', 'Continuous Voice'].map((m) => (
                            <button
                              key={m}
                              type="button"
                              onClick={() => {
                                setSelectedModelName(m);
                                setShowModelDropdown(false);
                              }}
                              className={`w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors ${
                                selectedModelName === m ? 'bg-zinc-800 text-white font-medium' : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
                              }`}
                            >
                              {m}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Row 2: Language */}
                  <div className="flex items-center justify-between text-xs py-1 border-t border-zinc-800/60 pt-3 relative">
                    <span className="text-zinc-200 font-medium">Language</span>
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setShowLangDropdown(!showLangDropdown)}
                        className="text-zinc-400 hover:text-zinc-200 font-medium flex items-center gap-1.5 transition-colors focus:outline-none"
                      >
                        <span>{selectedLanguageName}</span>
                        <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
                      </button>

                      {showLangDropdown && (
                        <div className="absolute right-0 bottom-7 w-48 bg-zinc-900 border border-zinc-700/80 rounded-xl shadow-xl p-1 z-30 space-y-0.5">
                          {['Auto-detect', 'Tamil / Tanglish (ta-IN)', 'English (en-IN / en-US)'].map((l) => (
                            <button
                              key={l}
                              type="button"
                              onClick={() => {
                                setSelectedLanguageName(l);
                                setShowLangDropdown(false);
                              }}
                              className={`w-full text-left px-3 py-1.5 rounded-lg text-xs transition-colors ${
                                selectedLanguageName === l ? 'bg-zinc-800 text-white font-medium' : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
                              }`}
                            >
                              {l}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Row 3: Auto Voice Response Toggle */}
                  <div className="flex items-center justify-between text-xs py-1 border-t border-zinc-800/60 pt-3">
                    <span className="text-zinc-200 font-medium">Auto Voice Response</span>
                    <button
                      type="button"
                      onClick={() => setAutoVoiceResponse(!autoVoiceResponse)}
                      className={`w-10 h-5 flex items-center rounded-full p-0.5 transition-colors ${
                        autoVoiceResponse ? 'bg-emerald-500 justify-end' : 'bg-zinc-700 justify-start'
                      }`}
                    >
                      <span className="w-4 h-4 rounded-full bg-white shadow-sm" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: GENERAL (Assistant Identity & Operator Profile) */}
          {activeTab === 'general' && (
            <div className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar animate-fadeIn">
              <div className="px-8 py-5 border-b border-zinc-800/80 shrink-0">
                <h2 className="text-base font-semibold text-zinc-100">General</h2>
              </div>

              <div className="p-8 space-y-6">
                {/* Assistant Identity */}
                <div className="space-y-3">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                    Assistant Identity
                  </h3>
                  <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-1">
                    <span className="text-[11px] text-zinc-400">Current Name</span>
                    <div className="text-lg font-bold text-white uppercase">
                      {identity?.assistant_name || 'Seyal AI'}
                    </div>
                  </div>

                  <div className="space-y-2 pt-1">
                    <label className="block text-xs text-zinc-300">
                      Change Assistant Persona Name
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={targetName}
                        onChange={(e) => setTargetName(e.target.value)}
                        placeholder="e.g. Jarvis, Friday, Nova..."
                        className="flex-1 bg-zinc-800/60 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-zinc-500 font-sans"
                      />
                      <button
                        type="button"
                        disabled={!targetName.trim() || isChangingName}
                        onClick={handleNameChangeRequest}
                        className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 text-xs font-medium text-white rounded-xl transition-all"
                      >
                        {isChangingName ? 'Requesting...' : 'Change Name'}
                      </button>
                    </div>
                    {nameChangeStatus && (
                      <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-mono mt-2">
                        {nameChangeStatus}
                      </div>
                    )}
                  </div>
                </div>

                {/* Operator Profile */}
                <div className="space-y-3 pt-4 border-t border-zinc-800/80">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                    Operator Profile Details
                  </h3>

                  {profileMessage && (
                    <div
                      className={`p-3 rounded-xl border text-xs ${
                        profileMessage.isError
                          ? 'bg-red-950/40 border-red-500/30 text-red-300'
                          : 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
                      }`}
                    >
                      {profileMessage.text}
                    </div>
                  )}

                  <div className="space-y-3">
                    <div>
                      <label className="block text-[11px] text-zinc-400 mb-1">Full Name</label>
                      <input
                        type="text"
                        value={userNameInput}
                        onChange={(e) => setUserNameInput(e.target.value)}
                        placeholder="e.g. John Doe"
                        className="w-full bg-zinc-800/60 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-zinc-500"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] text-zinc-400 mb-1">Age</label>
                        <input
                          type="number"
                          min="1"
                          max="120"
                          value={userAgeInput}
                          onChange={(e) => setUserAgeInput(e.target.value)}
                          placeholder="e.g. 25"
                          className="w-full bg-zinc-800/60 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-zinc-500"
                        />
                      </div>

                      <div>
                        <label className="block text-[11px] text-zinc-400 mb-1">Gender</label>
                        <select
                          value={userGenderInput}
                          onChange={(e) => setUserGenderInput(e.target.value)}
                          className="w-full bg-zinc-800/60 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500 cursor-pointer"
                        >
                          <option value="male">Male</option>
                          <option value="female">Female</option>
                          <option value="other">Other</option>
                        </select>
                      </div>
                    </div>

                    <div className="flex justify-end pt-2">
                      <button
                        type="button"
                        onClick={handleUpdateUserProfile}
                        disabled={savingProfile || fetchingProfile}
                        className="px-5 py-2 bg-white text-zinc-950 font-semibold text-xs rounded-xl hover:bg-zinc-200 transition-all flex items-center gap-1.5"
                      >
                        <Save className="w-3.5 h-3.5" />
                        {savingProfile ? 'Saving...' : 'Save Profile'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: PERSONALIZATION (Wake Word & Aliases) */}
          {activeTab === 'personalization' && (
            <div className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar animate-fadeIn">
              <div className="px-8 py-5 border-b border-zinc-800/80 shrink-0">
                <h2 className="text-base font-semibold text-zinc-100">Personalization & Wake Words</h2>
              </div>

              <div className="p-8 space-y-6">
                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Primary Wake Word:</span>
                    <span className="font-mono text-cyan-300 font-bold">
                      "{identity?.wake_word || 'hey nexus'}"
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Voice Pipeline Status:</span>
                    <span className={`font-mono font-bold ${voicePipelineActive ? 'text-emerald-400' : 'text-zinc-500'}`}>
                      {voicePipelineActive ? 'ACTIVE' : 'IDLE'}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">TTS Synthesis Engine:</span>
                    <span className="font-mono text-zinc-300">
                      {voiceStatus?.pipeline?.tts_provider || 'Microsoft Edge Neural'}
                    </span>
                  </div>
                </div>

                <div className="flex justify-between items-center pt-2">
                  <span className="text-xs text-zinc-300">Continuous Voice Detection</span>
                  <button
                    type="button"
                    onClick={handleToggleVoicePipeline}
                    className={`px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1.5 transition-colors ${
                      voicePipelineActive
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30'
                        : 'bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700'
                    }`}
                  >
                    <Mic className="w-3.5 h-3.5" />
                    {voicePipelineActive ? 'Stop Pipeline' : 'Start Pipeline'}
                  </button>
                </div>

                {/* Wake Word Aliases */}
                <div className="space-y-3 pt-4 border-t border-zinc-800/80">
                  <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                    Wake Word Aliases ({identity?.aliases?.length || 0})
                  </h3>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newAlias}
                      onChange={(e) => setNewAlias(e.target.value)}
                      placeholder="Add new alias (e.g. computer, system)..."
                      className="flex-1 bg-zinc-800/60 border border-zinc-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-zinc-500 font-mono"
                    />
                    <button
                      type="button"
                      disabled={!newAlias.trim() || isAddingAlias}
                      onClick={handleAddAlias}
                      className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 disabled:opacity-40 text-xs font-medium text-white rounded-xl transition-all flex items-center gap-1"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add
                    </button>
                  </div>

                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {!identity?.aliases || identity.aliases.length === 0 ? (
                      <div className="text-xs text-zinc-500 py-3 text-center">
                        No secondary aliases configured.
                      </div>
                    ) : (
                      identity.aliases.map((alias) => (
                        <div
                          key={alias}
                          className="flex items-center justify-between px-3 py-2 rounded-xl bg-zinc-900/60 border border-zinc-800 text-xs font-mono"
                        >
                          <span className="text-zinc-200">"{alias}"</span>
                          <button
                            type="button"
                            onClick={() => handleRemoveAlias(alias)}
                            className="text-zinc-500 hover:text-rose-400 p-1 transition-colors"
                            title="Remove Alias"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: SAFETY & SECURITY */}
          {(activeTab === 'safety' || activeTab === 'security_login') && (
            <div className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar animate-fadeIn">
              <div className="px-8 py-5 border-b border-zinc-800/80 shrink-0">
                <h2 className="text-base font-semibold text-zinc-100">Safety & Security</h2>
              </div>

              <div className="p-8 space-y-4">
                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
                    <Shield className="w-4 h-4 text-cyan-400" />
                    <span>Two-Step Human Authorization Guards</span>
                  </div>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    High-risk OS actions (deleting files, terminal execution, permanent settings changes) require explicit interactive confirmation before execution.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
                    <Radio className="w-4 h-4 text-purple-400" />
                    <span>Inner Application Protection</span>
                  </div>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Strict prohibition guards prevent the agent from terminating or minimizing its own window during workflow execution.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* OTHER TABS: Placeholder matching standard settings */}
          {!['voice', 'general', 'personalization', 'safety', 'security_login'].includes(activeTab) && (
            <div className="flex-1 flex flex-col h-full animate-fadeIn">
              <div className="px-8 py-5 border-b border-zinc-800/80 shrink-0">
                <h2 className="text-base font-semibold text-zinc-100 capitalize">
                  {activeTab.replace('_', ' ')}
                </h2>
              </div>
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <div className="w-12 h-12 rounded-2xl bg-zinc-800/60 border border-zinc-700/40 flex items-center justify-center text-zinc-400 mb-3">
                  <Settings className="w-6 h-6" />
                </div>
                <p className="text-xs text-zinc-400 max-w-sm">
                  Standard preferences for this category are managed automatically by the NEXUS OS layer.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
