import React, { useState } from 'react';
import { FolderOpen, Search, FileText } from 'lucide-react';
import { GlassCard } from '../common/GlassCard';
import { useNexus } from '../../context/NexusContext';
import { api } from '../../services/api';

export const FilesView: React.FC = () => {
  const { addActivity } = useNexus();
  const [searchPattern, setSearchPattern] = useState('');
  const [filePath, setFilePath] = useState('~');
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [outputMessage, setOutputMessage] = useState<string | null>(null);

  const handleSearchFiles = async () => {
    if (!searchPattern.trim()) return;
    setIsProcessing(true);
    setFileContent(null);
    try {
      addActivity({
        type: 'tool_exec',
        title: 'Searching Files',
        detail: `Executing search_files with query: '${searchPattern}'`,
        status: 'info',
      });
      const res = await api.executeLaptopTool(
        'search_files',
        { query: searchPattern, directory: filePath || '~' },
        true
      );
      setFileContent(res.output || JSON.stringify(res.data, null, 2));
      setOutputMessage('Search query executed.');
    } catch (err: any) {
      setOutputMessage(`Search failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReadFile = async () => {
    if (!filePath.trim()) return;
    setIsProcessing(true);
    setFileContent(null);
    try {
      addActivity({
        type: 'tool_exec',
        title: 'Reading File',
        detail: `Executing read_file on: '${filePath}'`,
        status: 'info',
      });
      const res = await api.executeLaptopTool('read_file', { path: filePath }, true);
      setFileContent(res.output || JSON.stringify(res.data, null, 2));
      setOutputMessage('File read complete.');
    } catch (err: any) {
      setOutputMessage(`Read failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-8">
      <div>
        <h2 className="font-display font-black text-xl text-white tracking-wider flex items-center gap-2">
          <FolderOpen className="w-5 h-5 text-cyan-400" />
          FILE SYSTEM INTELLIGENCE & ACCESS
        </h2>
        <p className="font-tech text-xs text-slate-400 uppercase tracking-widest mt-1">
          Direct File Operations with Safety Sandbox Boundaries
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Controls Card */}
        <GlassCard className="p-5 space-y-4">
          <h3 className="font-display font-bold text-sm text-white tracking-wider">
            FILE OPERATIONS
          </h3>

          <div className="space-y-2">
            <label className="block font-tech text-xs text-slate-400 uppercase">
              Target File / Directory Path
            </label>
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="e.g. C:\Users or ~"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="space-y-2">
            <label className="block font-tech text-xs text-slate-400 uppercase">
              Search Query Pattern
            </label>
            <input
              type="text"
              value={searchPattern}
              onChange={(e) => setSearchPattern(e.target.value)}
              placeholder="e.g. *.txt or report"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2">
            <button
              type="button"
              disabled={isProcessing}
              onClick={handleSearchFiles}
              className="cyber-btn text-xs py-2 justify-center"
            >
              <Search className="w-3.5 h-3.5" />
              Search Files
            </button>

            <button
              type="button"
              disabled={isProcessing}
              onClick={handleReadFile}
              className="cyber-btn cyber-btn-primary text-xs py-2 justify-center"
            >
              <FileText className="w-3.5 h-3.5" />
              Read File
            </button>
          </div>

          {outputMessage && (
            <div className="font-tech text-xs text-cyan-300 p-2.5 rounded bg-cyan-500/10 border border-cyan-500/30">
              {outputMessage}
            </div>
          )}
        </GlassCard>

        {/* File Content / Results Viewer */}
        <GlassCard glow corners className="lg:col-span-2 p-5 flex flex-col min-h-[400px]">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <span className="font-tech font-bold text-xs uppercase tracking-wider text-slate-300">
              OUTPUT VIEWER & INSPECTOR
            </span>
            <span className="font-mono text-[11px] text-cyan-400">
              {filePath}
            </span>
          </div>

          <div className="flex-1 mt-4 p-4 rounded-lg bg-slate-950/90 border border-slate-800 font-mono text-xs text-slate-200 overflow-auto whitespace-pre-wrap">
            {fileContent ? (
              fileContent
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500">
                Execute a file search or inspect a document path to view output here.
              </div>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};
