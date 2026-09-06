import React from 'react';
import { useNexus } from '../../context/NexusContext';
import { SimpleChatbotSidebar } from './SimpleChatbotSidebar';
import { ConvoAgentSidebar } from './ConvoAgentSidebar';

interface SidebarProps {
  onSelectPrompt?: (promptText: string) => void;
}

/**
 * Root Sidebar Component — Both sidebars stay permanently mounted.
 * Visibility is toggled via CSS only (no unmount/remount on mode switch),
 * which means no redundant API fetch when the user toggles between modes.
 */
export const Sidebar: React.FC<SidebarProps> = ({ onSelectPrompt }) => {
  const { isComputerUseActive } = useNexus();

  return (
    <>
      {/* Always mounted — hidden when computer-use is active */}
      <div style={{ display: isComputerUseActive ? 'none' : 'contents' }}>
        <SimpleChatbotSidebar onSelectPrompt={onSelectPrompt} />
      </div>

      {/* Always mounted — hidden when simple chatbot is active */}
      <div style={{ display: isComputerUseActive ? 'contents' : 'none' }}>
        <ConvoAgentSidebar onSelectPrompt={onSelectPrompt} />
      </div>
    </>
  );
};
