import React from 'react';
import { useNexus } from '../../context/NexusContext';
import { SimpleChatbotSettingsView } from './SimpleChatbotSettingsView';
import { ConvoAgentSettingsView } from './ConvoAgentSettingsView';

/**
 * Root Settings View:
 * Dynamically renders the dedicated settings screen:
 * - SimpleChatbotSettingsView: Clean operator profile settings for Simple Chatbot
 * - ConvoAgentSettingsView: Full advanced system, identity, voice pipeline & wake words configuration for Conversational Computer Use Agent
 */
export const SettingsView: React.FC = () => {
  const { isComputerUseActive } = useNexus();

  if (isComputerUseActive) {
    return <ConvoAgentSettingsView />;
  }

  return <SimpleChatbotSettingsView />;
};
