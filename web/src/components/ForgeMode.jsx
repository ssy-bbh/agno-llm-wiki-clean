import { useState } from 'react'
import ForceGraph from './ForceGraph'
import CyberForge from './CyberForge'
import Inbox from './Inbox'
import Radar from './Radar'
import AuditLog from './AuditLog'

export default function ForgeMode() {
  const [selectedNode, setSelectedNode] = useState(null)
  const [activeTab, setActiveTab] = useState('forge')

  return (
    <div className="flex h-full bg-slate-900">
      {/* Left: Force Graph (70%) */}
      <div className="w-[70%] relative">
        <ForceGraph onNodeClick={setSelectedNode} selectedNode={selectedNode} />
        {selectedNode && (
          <div className="absolute top-4 left-4 glass rounded-xl px-4 py-2 animate-fade-in">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-sm text-cyan-300 font-medium">{selectedNode}</span>
              <button
                onClick={() => setSelectedNode(null)}
                className="ml-2 text-slate-500 hover:text-slate-300 text-xs"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Right: Control Panel (30%) */}
      <div className="w-[30%] border-l border-slate-700/60 flex flex-col overflow-hidden bg-slate-950/50">
        {/* Tab bar */}
        <div className="flex border-b border-slate-700/60">
          {['forge', 'inbox', 'radar', 'log'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2.5 text-[11px] font-medium uppercase tracking-wider transition-all border-b-2 ${
                activeTab === tab
                  ? 'text-cyan-400 border-cyan-400/50 bg-cyan-500/5'
                  : 'text-slate-500 border-transparent hover:text-slate-400'
              }`}
            >
              {tab === 'forge' && '☁️ 熔炉'}
              {tab === 'inbox' && '✅ 审批'}
              {tab === 'radar' && '📡 雷达'}
              {tab === 'log' && '📜 档案'}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'forge' && <CyberForge />}
          {activeTab === 'inbox' && <Inbox />}
          {activeTab === 'radar' && <Radar />}
          {activeTab === 'log' && <AuditLog />}
        </div>
      </div>
    </div>
  )
}
