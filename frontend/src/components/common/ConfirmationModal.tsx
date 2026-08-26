import React, { useState } from 'react';
import { AlertTriangle, CheckCircle, XCircle, ShieldAlert } from 'lucide-react';
import { useNexus } from '../../context/NexusContext';

export const ConfirmationModal: React.FC = () => {
  const { pendingConfirmationPrompt, confirmAction, cancelPendingConfirmation } = useNexus();
  const [isProcessing, setIsProcessing] = useState(false);

  if (!pendingConfirmationPrompt) return null;

  const handleConfirm = async (approved: boolean) => {
    setIsProcessing(true);
    try {
      await confirmAction(approved);
    } catch {
      // Handled in context
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
      <div className="glass-panel p-6 max-w-lg w-full border-cyan-400/60 shadow-2xl relative tech-corners">
        <div className="flex items-center gap-3 mb-4 text-amber-400">
          <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30">
            <ShieldAlert className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h3 className="font-display font-bold text-lg text-white">
              AUTHORIZATION REQUIRED
            </h3>
            <p className="font-tech text-xs tracking-wider text-amber-400 uppercase">
              Two-Step Identity & Security Verification
            </p>
          </div>
        </div>

        <div className="p-4 my-3 rounded-lg bg-slate-900/80 border border-slate-800 font-mono text-sm text-cyan-200 leading-relaxed">
          <div className="flex items-start gap-2 mb-1 text-slate-400 text-xs uppercase font-sans">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5" />
            <span>Pending System Directive</span>
          </div>
          {pendingConfirmationPrompt}
        </div>

        <p className="text-xs text-slate-400 mb-6 font-tech">
          This action alters the assistant identity or system state. Confirm to apply immediately or reject to abort.
        </p>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            disabled={isProcessing}
            onClick={() => cancelPendingConfirmation()}
            className="cyber-btn cyber-btn-danger px-4 py-2"
          >
            <XCircle className="w-4 h-4" />
            Reject / Abort
          </button>
          <button
            type="button"
            disabled={isProcessing}
            onClick={() => handleConfirm(true)}
            className="cyber-btn cyber-btn-primary px-5 py-2"
          >
            <CheckCircle className="w-4 h-4" />
            {isProcessing ? 'Authorizing...' : 'Authorize Change'}
          </button>
        </div>
      </div>
    </div>
  );
};
