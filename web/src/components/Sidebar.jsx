import { useState } from 'react'
import { mockSandboxes } from '../data/mockData'

export default function Sidebar({ mode, onModeChange, selectedSandbox, onSandboxSelect }) {
  return (
    <aside className="w-[260px] min-w-[260px] h-screen bg-slate-950/80 border-r border-slate-700/60 flex flex-col relative scanline overflow-hidden">
      {/* Scanline overlay */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-cyan-500/[0.02] to-transparent h-8 animate-scan" />

      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-700/60">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🧠</span>
          <h1 className="text-lg font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent tracking-wide">
            LLM-Wiki OS
          </h1>
        </div>
        <p className="text-[10px] text-slate-500 mt-1 font-mono tracking-widest uppercase">Knowledge Graph Engine</p>
      </div>

      {/* Mode Toggle */}
      <div className="px-4 py-4 border-b border-slate-700/60">
        <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-2 font-semibold">运行模式</p>
        <div className="flex rounded-lg bg-slate-800/60 p-1 border border-slate-700/40">
          <button
            onClick={() => onSandboxSelect(null)}
            className={`flex-1 py-1.5 px-2 text-xs rounded-md transition-all duration-200 font-medium ${
              mode === 'query' && selectedSandbox === null
                ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.3)]'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            🗣️ 探求
          </button>
          <button
            onClick={() => onSandboxSelect(null)}
            className={`flex-1 py-1.5 px-2 text-xs rounded-md transition-all duration-200 font-medium ${
              mode === 'forge' && selectedSandbox === null
                ? 'bg-cyan-500/20 text-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.3)]'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            🕸️ 织网
          </button>
        </div>
      </div>

      {/* Workspace Radar */}
      <div className="flex-1 px-4 py-4 overflow-hidden">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">工作区沙箱</p>
          <span className="text-[9px] text-emerald-500/80 font-mono">{mockSandboxes.length} active</span>
        </div>
        <div className="space-y-1.5">
          {mockSandboxes.map((sb) => (
            <button
              key={sb.id}
              onClick={() => onSandboxSelect(sb.id === selectedSandbox ? null : sb.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all duration-200 group ${
                sb.id === selectedSandbox
                  ? 'bg-slate-700/40 border-cyan-500/40 glow-cyan'
                  : 'bg-slate-800/30 border-slate-700/30 hover:border-slate-600/50 hover:bg-slate-800/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-xs font-mono font-medium ${
                  sb.id === selectedSandbox ? 'text-cyan-300' : 'text-slate-300'
                }`}>
                  {sb.name}
                </span>
                <span className={`w-1.5 h-1.5 rounded-full ${
                  sb.status === 'active' ? 'bg-emerald-400 animate-pulse' :
                  sb.status === 'processing' ? 'bg-amber-400 animate-pulse' : 'bg-slate-500'
                }`} />
              </div>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-slate-500">{sb.files} files</span>
                <span className="text-[10px] text-slate-600">{sb.lastUpdate}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-700/60">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] text-slate-500 font-mono">v0.1.0 · Online</span>
        </div>
      </div>
    </aside>
  )
}
