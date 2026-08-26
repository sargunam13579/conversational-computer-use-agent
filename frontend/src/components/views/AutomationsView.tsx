import React, { useState } from 'react';
import { Cpu, Play, ArrowRight, Sparkles, Layers } from 'lucide-react';
import { GlassCard } from '../common/GlassCard';
import { useNexus } from '../../context/NexusContext';
import { api } from '../../services/api';

export const AutomationsView: React.FC = () => {
  const { addActivity } = useNexus();
  const [goalText, setGoalText] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentPlan, setCurrentPlan] = useState<string[] | null>(null);

  const presetWorkflows = [
    {
      title: 'Workstation System Diagnostics',
      desc: 'Check CPU load, available tools, memory status, and log report.',
      steps: ['Get System Info', 'Query Volume Level', 'Verify DB Integrity'],
    },
    {
      title: 'Screen Capture & Analysis Pipeline',
      desc: 'Capture active window snapshot and inspect running desktop layout.',
      steps: ['Capture Screenshot', 'Analyze Window Dimensions', 'Store in Memory'],
    },
    {
      title: 'Cross-Device Handoff Routine',
      desc: 'Sync active workspace URLs and state to mobile companion.',
      steps: ['Capture Active URLs', 'Package State Payload', 'Dispatch Handoff'],
    },
  ];

  const handleRunAutomation = async (customGoal?: string) => {
    const goal = (customGoal || goalText).trim();
    if (!goal) return;

    setIsExecuting(true);
    setCurrentPlan([
      `Decomposing goal: "${goal}"`,
      'Evaluating dependencies and authorized tool scopes...',
      'Executing plan steps with verification...',
      'Validating final step outcomes...',
    ]);

    addActivity({
      type: 'tool_exec',
      title: 'Autonomous Goal Dispatched',
      detail: goal,
      status: 'info',
    });

    try {
      // Send directly to the brain chat endpoint which activates planner and tools
      const res = await api.sendMessage(`Please plan and execute this task: ${goal}`);
      setCurrentPlan((prev) => [
        ...(prev || []),
        'Execution completed successfully:',
        res.response,
      ]);
      addActivity({
        type: 'tool_exec',
        title: 'Plan Completed',
        detail: res.response.slice(0, 100),
        status: 'success',
      });
    } catch (err: any) {
      setCurrentPlan((prev) => [
        ...(prev || []),
        `⚠️ Plan failed: ${err?.response?.data?.detail || err.message}`,
      ]);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-8">
      <div>
        <h2 className="font-display font-black text-xl text-white tracking-wider flex items-center gap-2">
          <Cpu className="w-5 h-5 text-cyan-400" />
          AUTONOMOUS MULTI-STEP PLANNER & AUTOMATIONS
        </h2>
        <p className="font-tech text-xs text-slate-400 uppercase tracking-widest mt-1">
          Dependency-ordered Task Decomposition, Variable Passing, and Verified Results
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Dispatcher */}
        <GlassCard glow corners className="p-5 space-y-4">
          <h3 className="font-display font-bold text-sm text-white tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            DISPATCH COMPOUND GOAL
          </h3>

          <div className="space-y-2">
            <label className="block font-tech text-xs text-slate-400 uppercase">
              Compound Task Description
            </label>
            <textarea
              rows={3}
              value={goalText}
              onChange={(e) => setGoalText(e.target.value)}
              placeholder="e.g. Inspect my system info, check if volume is muted, and summarize workstation health."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs font-sans text-white focus:outline-none focus:border-cyan-400 resize-none"
            />
          </div>

          <button
            type="button"
            disabled={!goalText.trim() || isExecuting}
            onClick={() => handleRunAutomation()}
            className="cyber-btn cyber-btn-primary w-full justify-center text-xs py-2.5"
          >
            <Play className="w-4 h-4" />
            {isExecuting ? 'Planning & Executing...' : 'Execute Autonomous Plan'}
          </button>

          <div className="pt-3 border-t border-slate-800 space-y-3">
            <span className="font-tech text-xs font-bold text-slate-400 uppercase">
              PRESET MACRO WORKFLOWS
            </span>

            <div className="space-y-2">
              {presetWorkflows.map((wf, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    setGoalText(wf.title);
                    handleRunAutomation(wf.title);
                  }}
                  className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 hover:border-cyan-400/40 cursor-pointer transition-all space-y-1 group"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-tech font-bold text-xs text-white group-hover:text-cyan-300">
                      {wf.title}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-300 transition-transform group-hover:translate-x-1" />
                  </div>
                  <p className="text-[11px] text-slate-400 font-sans">{wf.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>

        {/* Right Planner Visualizer */}
        <GlassCard className="lg:col-span-2 p-5 flex flex-col min-h-[420px] border-slate-800">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <span className="font-tech font-bold text-xs uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              GRAPH DECOMPOSITION & PLAN MONITOR
            </span>
            {isExecuting && (
              <span className="font-tech text-xs text-cyan-400 animate-pulse">
                PLANNER ACTIVE
              </span>
            )}
          </div>

          <div className="flex-1 mt-4 p-4 rounded-lg bg-slate-950/90 border border-slate-800 font-mono text-xs text-slate-200 overflow-y-auto space-y-2">
            {currentPlan ? (
              currentPlan.map((step, idx) => (
                <div key={idx} className="flex items-start gap-2.5 leading-relaxed">
                  <span className="text-cyan-400 mt-0.5">▸</span>
                  <span className="whitespace-pre-wrap">{step}</span>
                </div>
              ))
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 text-center">
                <p>No active execution plan running.</p>
                <p className="text-[11px] mt-1">
                  Dispatch a goal above to watch the autonomous planner decompose and verify multi-step tasks.
                </p>
              </div>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};
