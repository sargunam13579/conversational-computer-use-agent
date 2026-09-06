import React, { useState, useEffect } from 'react';
import { Settings, Save, UserCheck } from 'lucide-react';
import { GlassCard } from '../common/GlassCard';
import { useNexus } from '../../context/NexusContext';
import { api } from '../../services/api';

export const SimpleChatbotSettingsView: React.FC = () => {
  const { identity, refreshState, addActivity } = useNexus();

  // User profile details state
  const [userNameInput, setUserNameInput] = useState(identity?.user_name || '');
  const [userAgeInput, setUserAgeInput] = useState('');
  const [userGenderInput, setUserGenderInput] = useState('male');
  const [fetchingProfile, setFetchingProfile] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{ text: string; isError: boolean } | null>(null);

  // Fetch current database profile on mount/identity load
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
        console.warn('Failed to load profile details in simple chatbot settings:', err);
        setUserNameInput(identity?.user_name || '');
      } finally {
        setFetchingProfile(false);
      }
    };
    fetchProfile();
  }, [identity]);

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

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-8 animate-fadeIn">
      {/* Page Title */}
      <div>
        <h2 className="font-display font-black text-xl text-white tracking-wider flex items-center gap-2">
          <Settings className="w-5 h-5 text-cyan-400" />
          SEYAL AI PROFILE SETTINGS
        </h2>
        <p className="font-tech text-xs text-slate-400 uppercase tracking-widest mt-1">
          Operator Designation & Profile Details
        </p>
      </div>

      {/* Operator Profile Card */}
      <GlassCard glow corners className="p-6 space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <UserCheck className="w-5 h-5 text-cyan-400" />
            <h3 className="font-display font-bold text-sm text-white tracking-wider">
              OPERATOR DESIGNATION & PROFILE DETAILS
            </h3>
          </div>
        </div>

        {profileMessage && (
          <div
            className={`p-3 rounded-lg border text-xs font-sans animate-fadeIn ${
              profileMessage.isError
                ? 'bg-red-950/40 border-red-500/30 text-red-300'
                : 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
            }`}
          >
            {profileMessage.text}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-300 font-tech mb-1.5 uppercase font-semibold">
              Full Name
            </label>
            <input
              type="text"
              value={userNameInput}
              onChange={(e) => setUserNameInput(e.target.value)}
              placeholder="e.g. Sargunam"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-400 font-sans transition-colors"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-300 font-tech mb-1.5 uppercase font-semibold">
                Age
              </label>
              <input
                type="number"
                min="1"
                max="120"
                value={userAgeInput}
                onChange={(e) => setUserAgeInput(e.target.value)}
                placeholder="e.g. 20"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-400 font-sans transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs text-slate-300 font-tech mb-1.5 uppercase font-semibold">
                Gender
              </label>
              <select
                value={userGenderInput}
                onChange={(e) => setUserGenderInput(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-cyan-300 focus:outline-none focus:border-cyan-400 font-sans cursor-pointer transition-colors"
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
              className="cyber-btn text-xs px-6 py-2.5 flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              {savingProfile ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </div>
      </GlassCard>
    </div>
  );
};
