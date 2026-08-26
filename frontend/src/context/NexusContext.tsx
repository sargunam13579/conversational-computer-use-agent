import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api } from '../services/api';
import type {
  HealthResponse,
  IdentityResponse,
  LaptopStatusResponse,
  DeviceNode,
  ActivityEvent,
  MessageItem,
} from '../types';

export type NavView =
  | 'dashboard'
  | 'assistant'
  | 'computer_use'
  | 'system'
  | 'applications'
  | 'files'
  | 'devices'
  | 'automations'
  | 'activity'
  | 'settings';

export const getWelcomeGreetingText = (userName = 'Sargunam'): string => {
  const displayUser = userName && userName.trim() && userName !== 'User' ? userName.trim() : 'Sargunam';
  return `Hey ${displayUser}! Welcome back da. Naan ready. Sollu, enna pannalam?`;
};

export const createWelcomeMessage = (userName = 'Sargunam', _assistantName = 'JARVIS'): MessageItem => {
  return {
    role: 'assistant',
    content: getWelcomeGreetingText(userName),
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    model_used: 'gemini-2.5-flash',
  };
};

interface NexusContextType {
  activeView: NavView;
  setActiveView: (view: NavView) => void;
  identity: IdentityResponse | null;
  health: HealthResponse | null;
  laptopStatus: LaptopStatusResponse | null;
  devices: DeviceNode[];
  activities: ActivityEvent[];
  pendingConfirmationPrompt: string | null;
  isBackendConnected: boolean;
  isLoading: boolean;
  isComputerUseActive: boolean;
  setIsComputerUseActive: (active: boolean) => void;
  activeConversationId: string | null;
  setActiveConversationId: (id: string | null) => void;
  messages: MessageItem[];
  setMessages: React.Dispatch<React.SetStateAction<MessageItem[]>>;
  simpleMessages: MessageItem[];
  setSimpleMessages: React.Dispatch<React.SetStateAction<MessageItem[]>>;
  computerUseMessages: MessageItem[];
  setComputerUseMessages: React.Dispatch<React.SetStateAction<MessageItem[]>>;
  simpleConversationId: string | null;
  setSimpleConversationId: (id: string | null) => void;
  computerUseConversationId: string | null;
  setComputerUseConversationId: (id: string | null) => void;
  refreshState: () => Promise<void>;
  requestNameChange: (targetName: string) => Promise<string>;
  confirmAction: (confirmed: boolean) => Promise<{ success: boolean; message: string }>;
  cancelPendingConfirmation: () => Promise<void>;
  addActivity: (event: Omit<ActivityEvent, 'id' | 'timestamp'>) => void;
  triggerEmergencyStop: () => void;
  resetChatContext: () => Promise<void>;
}

const NexusContext = createContext<NexusContextType | undefined>(undefined);

export const NexusProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeView, setActiveView] = useState<NavView>('assistant');
  const [isComputerUseActive, setIsComputerUseActive] = useState<boolean>(false);
  const [identity, setIdentity] = useState<IdentityResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [laptopStatus, setLaptopStatus] = useState<LaptopStatusResponse | null>(null);
  const [devices, setDevices] = useState<DeviceNode[]>([]);
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [pendingConfirmationPrompt, setPendingConfirmationPrompt] = useState<string | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Separate conversation states for Simple Chatbot vs Conversational Computer-Use Agent
  const [simpleConversationId, setSimpleConversationId] = useState<string | null>(null);
  const [computerUseConversationId, setComputerUseConversationId] = useState<string | null>(null);

  const [simpleMessages, setSimpleMessages] = useState<MessageItem[]>([]);
  const [computerUseMessages, setComputerUseMessages] = useState<MessageItem[]>([]);

  const activeConversationId = isComputerUseActive ? computerUseConversationId : simpleConversationId;
  const setActiveConversationId = (id: string | null) => {
    if (isComputerUseActive) {
      setComputerUseConversationId(id);
    } else {
      setSimpleConversationId(id);
    }
  };

  const messages = isComputerUseActive ? computerUseMessages : simpleMessages;
  const setMessages: React.Dispatch<React.SetStateAction<MessageItem[]>> = (val) => {
    if (isComputerUseActive) {
      setComputerUseMessages(val);
    } else {
      setSimpleMessages(val);
    }
  };

  const userHasInteractedRef = useRef<boolean>(false);

  const addActivity = useCallback((event: Omit<ActivityEvent, 'id' | 'timestamp'>) => {
    const newEvent: ActivityEvent = {
      ...event,
      id: `act_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
      timestamp: new Date().toLocaleTimeString(),
    };
    setActivities((prev) => [newEvent, ...prev.slice(0, 49)]);
  }, []);

  const refreshState = useCallback(async () => {
    try {
      const [healthData, identityData] = await Promise.allSettled([
        api.getHealth(),
        api.getIdentity(),
      ]);

      if (healthData.status === 'fulfilled') {
        setHealth(healthData.value);
        setIsBackendConnected(true);
      } else {
        setIsBackendConnected(false);
      }

      if (identityData.status === 'fulfilled') {
        const idData = identityData.value;
        setIdentity(idData);

        if (idData.has_pending_confirmation && !pendingConfirmationPrompt) {
          setPendingConfirmationPrompt(
            idData.pending_action
              ? `Action pending: ${idData.pending_action}`
              : 'Confirmation required for pending action'
          );
        } else if (!idData.has_pending_confirmation) {
          setPendingConfirmationPrompt(null);
        }
      }

      // Best effort telemetry
      try {
        const laptop = await api.getLaptopStatus();
        setLaptopStatus(laptop);
      } catch {
        // Laptop telemetry optional
      }

      try {
        const devData = await api.listDevices();
        setDevices(devData.devices || []);
      } catch {
        // Devices list optional
      }
    } catch (err) {
      console.error('Error refreshing state:', err);
      setIsBackendConnected(false);
    } finally {
      setIsLoading(false);
    }
  }, [pendingConfirmationPrompt]);

  useEffect(() => {
    refreshState();
    // Periodic status poll every 10 seconds
    const interval = setInterval(refreshState, 10000);
    return () => clearInterval(interval);
  }, [refreshState]);

  const requestNameChange = async (targetName: string): Promise<string> => {
    try {
      const res = await api.requestNameChange(targetName);
      setPendingConfirmationPrompt(res.confirmation_prompt);
      addActivity({
        type: 'identity',
        title: 'Identity Change Requested',
        detail: `Request initiated to rename assistant to '${targetName}'`,
        status: 'info',
      });
      await refreshState();
      return res.confirmation_prompt;
    } catch (err: any) {
      addActivity({
        type: 'identity',
        title: 'Rename Request Failed',
        detail: err?.response?.data?.detail || err.message,
        status: 'error',
      });
      throw err;
    }
  };

  const confirmAction = async (confirmed: boolean): Promise<{ success: boolean; message: string }> => {
    try {
      const res = await api.confirmPendingAction(confirmed);
      setPendingConfirmationPrompt(null);
      addActivity({
        type: 'identity',
        title: confirmed ? 'Action Approved' : 'Action Rejected',
        detail: res.message,
        status: confirmed ? 'success' : 'warning',
      });
      await refreshState();
      return { success: res.confirmed, message: res.message };
    } catch (err: any) {
      addActivity({
        type: 'identity',
        title: 'Confirmation Error',
        detail: err?.response?.data?.detail || err.message,
        status: 'error',
      });
      throw err;
    }
  };

  const cancelPendingConfirmation = async (): Promise<void> => {
    try {
      await api.cancelPendingConfirmation();
      setPendingConfirmationPrompt(null);
      await refreshState();
    } catch (err) {
      console.error('Cancel pending failed', err);
    }
  };

  const triggerEmergencyStop = () => {
    addActivity({
      type: 'security',
      title: '🚨 EMERGENCY KILL SWITCH TRIGGERED',
      detail: 'Manual emergency stop triggered by operator',
      status: 'error',
    });
    // Attempt resetting chat or canceling any confirmation
    api.cancelPendingConfirmation().catch(() => {});
  };

  const resetChatContext = async () => {
    try {
      if (!isComputerUseActive) {
        await api.resetChat();
      }
      setMessages([]);
      setActiveConversationId(null);
      userHasInteractedRef.current = false;
      addActivity({
        type: 'chat',
        title: isComputerUseActive ? 'Agent Session Reset' : 'Context Reset',
        detail: isComputerUseActive ? 'Computer-Use Agent session cleared.' : 'Conversation session cleared.',
        status: 'info',
      });
    } catch (err: any) {
      console.error('Reset chat failed:', err);
    }
  };

  return (
    <NexusContext.Provider
      value={{
        activeView,
        setActiveView,
        isComputerUseActive,
        setIsComputerUseActive,
        identity,
        health,
        laptopStatus,
        devices,
        activities,
        pendingConfirmationPrompt,
        isBackendConnected,
        isLoading,
        activeConversationId,
        setActiveConversationId,
        messages,
        setMessages,
        simpleMessages,
        setSimpleMessages,
        computerUseMessages,
        setComputerUseMessages,
        simpleConversationId,
        setSimpleConversationId,
        computerUseConversationId,
        setComputerUseConversationId,
        refreshState,
        requestNameChange,
        confirmAction,
        cancelPendingConfirmation,
        addActivity,
        triggerEmergencyStop,
        resetChatContext,
      }}
    >
      {children}
    </NexusContext.Provider>
  );
};

export const useNexus = (): NexusContextType => {
  const context = useContext(NexusContext);
  if (!context) {
    throw new Error('useNexus must be used within a NexusProvider');
  }
  return context;
};

